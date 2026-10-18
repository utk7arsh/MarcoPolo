"""Marco server prototype (POC 26): one-photo registration with a retake check, and 1 fps frame detection.

Endpoints:
  POST /items    multipart: photo (JPEG), name -> {item_id, quality: ok|retake, reason, box}
  POST /frames   multipart: frame (JPEG), device_id, frame_id -> {frame_id, detections: [...]}, or 409 when a
                 newer frame from the same device arrived first (latest frame wins; the phone keeps the
                 camera pose + depth of every frame it sent and places boxes with THAT pose, see POC 23)
  GET  /items
Boxes are in the pixel coordinates of the uploaded image AFTER applying its EXIF orientation (POC 23: PIL and
OpenCV disagree on EXIF, so the server normalises once, here).

Presence ("is this item in the frame at all?", POC 25): at the item's best box, the photo logit + name logit,
a DINOv2 check of the crop against the registration crop, and, with two or more items registered, whether
the box looks more like this item than the user's other items. Thresholds come from calibrate().

Security: every route sits behind require_caller(), which fails closed (403) until a real verifier is wired.
Tests opt in with AUTH_TEST_BYPASS=1. The listener binds 127.0.0.1 only (main refuses anything else); see the
checklist at the end of POC 26's report before exposing it to any other machine.
"""
import io
import os
import threading
import time
import uuid

import numpy as np
import torch
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from PIL import Image, ImageOps

OWL = "google/owlv2-base-patch16-ensemble"
DINO = "facebook/dinov2-small"
MAX_SIDE = 960
DEV = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")

# Retake check (POC 25B): OWLv2's score for the item's name in the registration photo.
GATE_NAME_SCORE = float(os.environ.get("GATE_NAME_SCORE", "0.05"))
# Presence thresholds; calibrate() replaces these with values fitted on labelled frames.
THRESHOLDS = {"photo_name": float(os.environ.get("TH_PHOTO_NAME", "0")), "dino": float(os.environ.get("TH_DINO", "0")),
              "vs_others": float(os.environ.get("TH_VS_OTHERS", "-1e9"))}


def require_caller(request: Request):
    """Fail-closed authentication gate.

    No real verifier is wired yet, so every request is rejected unless the purpose-named test bypass is set.
    Wire ONE of these before the phone talks to this server (see the POC 26 checklist):
      - private: run behind `tailscale serve` on a tailnet with this app bound to 127.0.0.1, and verify the
        identity header that tailscale serve adds (only trustworthy because nothing else can reach the app);
      - public: verify signed ID tokens from a real identity provider (e.g. Sign in with Apple) here.
    """
    if os.environ.get("AUTH_TEST_BYPASS") == "1":
        return "test-caller"
    raise HTTPException(status_code=403, detail="authentication not configured: request rejected (fail-closed)")


class Models:
    def __init__(self):
        from transformers import AutoImageProcessor, AutoModel, Owlv2ForObjectDetection, Owlv2Processor
        self.proc = Owlv2Processor.from_pretrained(OWL)
        self.owl = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True).to(DEV).eval()
        self.dproc = AutoImageProcessor.from_pretrained(DINO)
        self.dino = AutoModel.from_pretrained(DINO, use_safetensors=True).to(DEV).eval()

    @torch.no_grad()
    def image_pass(self, im):
        fmap = self.owl.image_embedder(pixel_values=self.proc(images=im, return_tensors="pt")["pixel_values"].to(DEV))[0]
        feats = fmap.reshape(1, -1, fmap.shape[-1])
        return fmap, feats

    @torch.no_grad()
    def text_query(self, name):
        tok = self.proc(text=[[f"a photo of {name}"]], return_tensors="pt").to(DEV)
        return self.owl.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[None]

    @torch.no_grad()
    def dino_embed(self, crops):
        x = self.dproc(images=crops, return_tensors="pt").to(DEV)
        return torch.nn.functional.normalize(self.dino(**x).pooler_output, dim=-1)


def load_image(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)          # honour the orientation tag once, so every model sees the same pixels
    im = im.convert("RGB")
    s = MAX_SIDE / max(im.size)
    if s < 1:
        im = im.resize((round(im.width * s), round(im.height * s)))
    return im


def to_px(box, im):
    """OWLv2 box (cx, cy, w, h as fractions of the padded square) -> pixel box in `im`."""
    cx, cy, w, h = box
    side = max(im.size)
    x0, y0 = max(0.0, (cx - w / 2) * side), max(0.0, (cy - h / 2) * side)
    x1, y1 = min(float(im.width), (cx + w / 2) * side), min(float(im.height), (cy + h / 2) * side)
    return [x0, y0, max(x1, x0 + 4), max(y1, y0 + 4)]


class Store:
    def __init__(self, models):
        self.m = models
        self.items = {}            # item_id -> dict(name, q_img, q_txt, dino, box)
        self.meta = threading.Lock()   # bookkeeping only (fast)
        self.gpu = threading.Lock()    # one frame on the model at a time
        self.latest = {}           # device_id -> newest frame_id seen

    def register(self, name, im):
        m = self.m
        with self.gpu:
            return self._register(name, im)

    @torch.no_grad()
    def _register(self, name, im):
        m = self.m
        fmap, feats = m.image_pass(im)
        q_txt = m.text_query(name)
        tl = m.owl.class_predictor(image_feats=feats, query_embeds=q_txt)[0][0, :, 0]
        score = float(torch.sigmoid(tl).max())
        box = to_px(m.owl.box_predictor(feats, fmap)[0, int(tl.argmax())].tolist(), im)
        if score < GATE_NAME_SCORE:
            return dict(item_id=None, quality="retake", reason=f"can't see the {name} clearly (score {score:.3f})", box=box)
        crop = im.crop(tuple(int(v) for v in box))
        cfmap, cfeats = m.image_pass(crop)
        q_img = m.owl.embed_image_query(cfeats, cfmap)[0]
        item_id = uuid.uuid4().hex[:12]
        self.items[item_id] = dict(name=name, q_img=q_img, q_txt=q_txt, dino=m.dino_embed([crop])[0], box=box)
        return dict(item_id=item_id, quality="ok", reason="", box=box)

    def handle_frame(self, device_id, frame_id, data):
        """Latest frame wins: note the frame's arrival, wait for the model, and skip it if a newer frame from
        the same device arrived meanwhile (the phone only cares about the freshest view)."""
        with self.meta:
            self.latest[device_id] = max(frame_id, self.latest.get(device_id, -1))
        with self.gpu:
            with self.meta:
                if frame_id < self.latest[device_id]:
                    return None
            t0 = time.perf_counter()
            dets = self.detect(load_image(data))
        return dict(frame_id=frame_id, server_ms=round(1000 * (time.perf_counter() - t0), 1), detections=dets)

    def detect(self, im):
        m = self.m
        if not self.items:
            return []
        ids = list(self.items)
        Q = torch.cat([self.items[i]["q_img"] for i in ids], dim=1)
        T = torch.cat([self.items[i]["q_txt"] for i in ids], dim=1)
        fmap, feats = m.image_pass(im)
        with torch.no_grad():
            L = m.owl.class_predictor(image_feats=feats, query_embeds=Q)[0][0].cpu().numpy()      # (patches, items)
            Lt = m.owl.class_predictor(image_feats=feats, query_embeds=T)[0][0].cpu().numpy()
            boxes = m.owl.box_predictor(feats, fmap)[0].cpu().numpy()
        best = L.argmax(0)
        crops, out = [], []
        for q, iid in enumerate(ids):
            b = best[q]
            box = to_px(boxes[b].tolist(), im)
            crops.append(im.crop(tuple(int(v) for v in box)))
            out.append(dict(item_id=iid, name=self.items[iid]["name"], box_px=[round(v, 1) for v in box],
                            photo_name=float(L[b, q] + Lt[b, q]),
                            vs_others=float(L[b, q] - np.delete(L[b], q).max()) if len(ids) > 1 else None))
        E = m.dino_embed(crops)
        for q, iid in enumerate(ids):
            d = out[q]
            d["dino"] = float((E[q] * self.items[iid]["dino"]).sum())
            d["present"] = bool(d["photo_name"] >= THRESHOLDS["photo_name"] and d["dino"] >= THRESHOLDS["dino"]
                                and (d["vs_others"] is None or d["vs_others"] >= THRESHOLDS["vs_others"]))
        return out


app = FastAPI(title="Marco server prototype")
_state = {}


def store() -> Store:
    if "store" not in _state:
        _state["store"] = Store(Models())
    return _state["store"]


@app.post("/items")
def post_item(name: str = Form(...), photo: UploadFile = File(...), caller=Depends(require_caller)):
    return store().register(name.strip(), load_image(photo.file.read()))


@app.get("/items")
def get_items(caller=Depends(require_caller)):
    return [dict(item_id=i, name=v["name"]) for i, v in store().items.items()]


@app.post("/frames")
def post_frame(device_id: str = Form(...), frame_id: int = Form(...), frame: UploadFile = File(...), caller=Depends(require_caller)):
    out = store().handle_frame(device_id, frame_id, frame.file.read())
    if out is None:
        raise HTTPException(status_code=409, detail="superseded by a newer frame from this device")
    return out


def main():
    import uvicorn  # not needed for the in-process tests
    host = os.environ.get("HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(f"refusing to bind {host}: loopback only; reach it through `tailscale serve` (see server/README.md)")
    uvicorn.run(app, host=host, port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
