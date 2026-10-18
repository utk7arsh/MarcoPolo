"""Finding registered items in a frame.

OwlDetector   the real one (POC 22/25/26): OWLv2 image-guided search with the item's one registration photo, plus
              the presence check (photo + name logit, DINOv2 crop check, "looks more like this item than my other
              items"). Thresholds default to POC 26's calibration on ORBIT; refit them on your own props.
TruthDetector for synthetic sessions with ground truth: projects the true item positions into the frame (with
              misses and jitter), so the world model and the dashboard can be tested without any model.

Both return detections in the pixels of the UPRIGHT image they were given.
"""
import os

import numpy as np

from .. import geometry as G

TH = {"photo_name": float(os.environ.get("TH_PHOTO_NAME", "-2.426")), "dino": float(os.environ.get("TH_DINO", "0.38")),
      "vs_others": float(os.environ.get("TH_VS_OTHERS", "0.078"))}
GATE_NAME_SCORE = float(os.environ.get("GATE_NAME_SCORE", "0.05"))


def _device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class OwlDetector:
    OWL = "google/owlv2-base-patch16-ensemble"
    DINO = "facebook/dinov2-small"

    def __init__(self):
        import torch
        from transformers import AutoImageProcessor, AutoModel, Owlv2ForObjectDetection, Owlv2Processor
        self.torch = torch
        self.dev = _device()
        dtype = torch.float16 if self.dev == "cuda" else torch.float32
        self.proc = Owlv2Processor.from_pretrained(self.OWL)
        self.owl = Owlv2ForObjectDetection.from_pretrained(self.OWL, use_safetensors=True, dtype=dtype).to(self.dev).eval()
        self.dproc = AutoImageProcessor.from_pretrained(self.DINO)
        self.dino = AutoModel.from_pretrained(self.DINO, use_safetensors=True).to(self.dev).eval()
        self.dtype = dtype
        self.items = {}            # item_id -> dict(name, q_img, q_txt, dino)

    def _pass(self, im):
        px = self.proc(images=im, return_tensors="pt")["pixel_values"].to(self.dev, self.dtype)
        fmap = self.owl.image_embedder(pixel_values=px)[0]
        return fmap, fmap.reshape(1, -1, fmap.shape[-1])

    def _text(self, name):
        tok = self.proc(text=[[f"a photo of {name}"]], return_tensors="pt").to(self.dev)
        return self.owl.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[None].to(self.dtype)

    def _dino(self, crops):
        x = self.dproc(images=crops, return_tensors="pt").to(self.dev)
        return self.torch.nn.functional.normalize(self.dino(**x).pooler_output.float(), dim=-1)

    @staticmethod
    def _to_px(box, im):
        cx, cy, w, h = box
        side = max(im.size)
        x0, y0 = max(0.0, (cx - w / 2) * side), max(0.0, (cy - h / 2) * side)
        x1, y1 = min(float(im.width), (cx + w / 2) * side), min(float(im.height), (cy + h / 2) * side)
        return [x0, y0, max(x1, x0 + 4), max(y1, y0 + 4)]

    def register(self, item_id, name, im, gate=True):
        """One photo + name. gate=False for crops a person already labelled (Photon)."""
        with self.torch.no_grad():
            fmap, feats = self._pass(im)
            q_txt = self._text(name)
            tl = self.owl.class_predictor(image_feats=feats, query_embeds=q_txt)[0][0, :, 0]
            score = float(self.torch.sigmoid(tl.float()).max())
            box = self._to_px(self.owl.box_predictor(feats, fmap)[0, int(tl.argmax())].float().tolist(), im)
            if gate and score < GATE_NAME_SCORE:
                return dict(quality="retake", reason=f"can't see the {name} clearly (score {score:.3f})", box=box)
            crop = im.crop(tuple(int(v) for v in box)) if gate else im
            cf, cfe = self._pass(crop)
            q_img = self.owl.embed_image_query(cfe, cf)[0]
            self.items[item_id] = dict(name=name, q_img=q_img, q_txt=q_txt, dino=self._dino([crop])[0])
        return dict(quality="ok", reason="", box=box)

    def forget(self, item_id):
        self.items.pop(item_id, None)

    def detect(self, im, **_):
        if not self.items:
            return []
        ids = list(self.items)
        with self.torch.no_grad():
            Q = self.torch.cat([self.items[i]["q_img"] for i in ids], dim=1)
            Tq = self.torch.cat([self.items[i]["q_txt"] for i in ids], dim=1)
            fmap, feats = self._pass(im)
            L = self.owl.class_predictor(image_feats=feats, query_embeds=Q)[0][0].float().cpu().numpy()
            Lt = self.owl.class_predictor(image_feats=feats, query_embeds=Tq)[0][0].float().cpu().numpy()
            boxes = self.owl.box_predictor(feats, fmap)[0].float().cpu().numpy()
            best = L.argmax(0)
            crops, out = [], []
            for q, iid in enumerate(ids):
                b = best[q]
                box = self._to_px(boxes[b].tolist(), im)
                crops.append(im.crop(tuple(int(v) for v in box)))
                out.append(dict(item_id=iid, name=self.items[iid]["name"], box=[round(v, 1) for v in box],
                                photo_name=float(L[b, q] + Lt[b, q]),
                                vs_others=float(L[b, q] - np.delete(L[b], q).max()) if len(ids) > 1 else None))
            E = self._dino(crops)
        for q, iid in enumerate(ids):
            d = out[q]
            d["dino"] = float((E[q] * self.items[iid]["dino"]).sum())
            d["present"] = bool(d["photo_name"] >= TH["photo_name"] and d["dino"] >= TH["dino"]
                                and (d["vs_others"] is None or d["vs_others"] >= TH["vs_others"]))
            d["score"] = round(1 / (1 + np.exp(-(d["photo_name"] - TH["photo_name"]))), 3)
        return out


class TruthDetector:
    """Ground-truth detector for synthetic sessions: truth = {name: {"position": [x, y, z], "size": metres}}."""

    def __init__(self, truth, miss_rate=0.15, jitter=0.04, seed=0):
        self.truth = truth
        self.items = {}
        self.miss, self.jitter = miss_rate, jitter
        self.rng = np.random.default_rng(seed)

    def register(self, item_id, name, im=None, gate=True):
        if name not in self.truth:
            return dict(quality="retake", reason=f"no ground truth for {name}", box=None)
        self.items[item_id] = name
        return dict(quality="ok", reason="", box=None)

    def forget(self, item_id):
        self.items.pop(item_id, None)

    def detect(self, im, fr: G.Frame, k: int, jpeg_scale: float):
        out = []
        jw, jh = (im.height, im.width) if k % 2 else (im.width, im.height)   # size of the unrotated JPEG
        for iid, name in self.items.items():
            t = self.truth[name]
            c = np.asarray(t["position"], float) + np.array([0, t.get("size", 0.1) / 2, 0])
            uv, z = fr.project(c[None])
            (u, v), z = uv[0], float(z[0])
            if z < 0.15 or not (0 <= u < fr.W and 0 <= v < fr.H):
                continue
            seen = fr.depth_at(u, v, r=1, min_conf=1)
            if seen is not None and seen < z - 0.15:
                continue                                        # hidden behind something nearer
            if self.rng.uniform() < self.miss:
                continue
            s = fr.K[0, 0] * t.get("size", 0.1) / z
            j = self.rng.normal(0, self.jitter * s, 4)
            b = [(u - s / 2 + j[0]) * jpeg_scale, (v - s / 2 + j[1]) * jpeg_scale, (u + s / 2 + j[2]) * jpeg_scale, (v + s / 2 + j[3]) * jpeg_scale]
            out.append(dict(item_id=iid, name=name, box=[round(x, 1) for x in G.rotate_box(b, k, jw, jh)], present=True, score=0.9))
        return out
