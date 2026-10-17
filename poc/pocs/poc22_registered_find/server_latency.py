"""POC 22 add-on: what one camera frame costs on a server in deployment mode ("register once, find many").

bench.py's first runs re-encoded the registration photo on every frame, and OWLv2's stock post-processing
runs a Python NMS loop over 3,600 boxes. A server encodes each registered photo (and name) once, keeps the
embeddings, and pays one image pass per camera frame. This times exactly that for every method in the
chart, on a full-size 1440x1920 portrait phone frame (decoded once; JPEG decode and network excluded).
It checks that the cached OWLv2 path picks the same box as the full call, and counts OWLv2's
floating-point operations per frame so the time can be scaled to a cloud GPU.
Run from data/models (YOLOE weights and text encoders live there).
"""
import importlib.util
import io
import json
import statistics
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("poc22_bench", HERE / "bench.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
MODELS = ROOT / "data" / "models"
DEV = B.DEV
OWL = "google/owlv2-base-patch16-ensemble"
N = 20
ITEM = next(it for it in B.items() if it["name"] == "P778--keys")


def sync():
    if DEV == "mps":
        torch.mps.synchronize()


def timed(fn):
    ts = []
    for _ in range(N + 3):
        t0 = time.perf_counter()
        fn()
        sync()
        ts.append(time.perf_counter() - t0)
    return round(1000 * statistics.median(ts[3:]), 1)  # ms; first 3 runs are warm-up


def phone_frame():
    src = next((ROOT / "data" / "downloads" / "commons_keys").glob("Flat_white*/image.jpg"))
    im = Image.open(src).convert("RGB")
    s = max(1440 / im.width, 1920 / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)))
    x0, y0 = (im.width - 1440) // 2, (im.height - 1920) // 2
    return im.crop((x0, y0, x0 + 1440, y0 + 1920))


def jpeg_kb(im, long_side):
    s = long_side / max(im.size)
    buf = io.BytesIO()
    im.resize((round(im.width * s), round(im.height * s))).save(buf, "JPEG", quality=80)
    return round(buf.tell() / 1024)


def reg_crop(rf):
    return Image.open(ITEM["regdir"] / rf).convert("RGB").crop(tuple(int(v) for v in ITEM["reg"][rf]))


def owlv2(frame, dtype=torch.float32):
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL)
    model = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True, dtype=dtype).to(DEV).eval()
    with torch.no_grad():  # registration, once per item: 6 photos + the name
        q = []
        for rf in ITEM["reg_order"][:6]:
            qmap = model.image_embedder(pixel_values=proc(images=reg_crop(rf), return_tensors="pt")["pixel_values"].to(DEV, dtype))[0]
            q.append(model.embed_image_query(qmap.reshape(1, -1, qmap.shape[-1]), qmap)[0])
        tok = proc(text=[["a photo of keys"]], return_tensors="pt").to(DEV)
        temb = model.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[:, None, :].to(dtype)
    out = {}

    def frame_pass(queries, with_name):
        with torch.no_grad():
            pix = proc(images=frame, return_tensors="pt")["pixel_values"].to(DEV, dtype)
            fmap = model.image_embedder(pixel_values=pix)[0]
            feats = fmap.reshape(1, -1, fmap.shape[-1])
            s = model.class_predictor(image_feats=feats, query_embeds=queries)[0][0].max(dim=-1).values
            if with_name:
                s = s + model.class_predictor(image_feats=feats, query_embeds=temb)[0][0, :, 0]
            k = int(s.argmax())
            box = model.box_predictor(feats, fmap)[0, k].float().cpu()
        return pix, k, box

    out["img1_ms"] = timed(lambda: frame_pass(q[0], False))
    out["img6_name_ms"] = timed(lambda: frame_pass(torch.cat(q, dim=1), True))
    out["img1_name_ms"] = timed(lambda: frame_pass(q[0], True))
    out["name_only_ms"] = timed(lambda: frame_pass(temb, False))
    t0 = time.perf_counter()
    pix = proc(images=frame, return_tensors="pt")["pixel_values"].to(DEV, dtype)
    sync()
    out["preprocess_ms"] = round(1000 * (time.perf_counter() - t0), 1)
    _, k, box = frame_pass(q[0], False)
    with torch.no_grad():
        qpix = proc(images=reg_crop(ITEM["reg_order"][0]), return_tensors="pt")["pixel_values"].to(DEV, dtype)
        full = model.image_guided_detection(pixel_values=pix, query_pixel_values=qpix)
    out["top_box_same_as_full_call"] = int(full.logits[0, :, 0].argmax()) == k
    return out


def owlv2_tflops(frame):
    from torch.utils.flop_counter import FlopCounterMode
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL)
    model = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True, attn_implementation="eager").eval()
    with torch.no_grad():
        qmap = model.image_embedder(pixel_values=proc(images=reg_crop(ITEM["reg_order"][0]), return_tensors="pt")["pixel_values"])[0]
        qemb = model.embed_image_query(qmap.reshape(1, -1, qmap.shape[-1]), qmap)[0]
        pix = proc(images=frame, return_tensors="pt")["pixel_values"]
        fc = FlopCounterMode(display=False)
        with fc:
            fmap = model.image_embedder(pixel_values=pix)[0]
            feats = fmap.reshape(1, -1, fmap.shape[-1])
            model.class_predictor(image_feats=feats, query_embeds=qemb)
            model.box_predictor(feats, fmap)
    return round(fc.get_total_flops() / 1e12, 3)


def yoloe_vp(bgr, weights, nref):
    from ultralytics import YOLOE
    m = YOLOE(str(MODELS / weights))
    pes = []
    for rf in ITEM["reg_order"][:nref]:  # registration, once per item
        m.predict(bgr, refer_image=str(ITEM["regdir"] / rf), visual_prompts={"bboxes": np.array([ITEM["reg"][rf]]), "cls": np.array([0])},
                  conf=0.001, verbose=False, device=DEV)
        pes.append(m.model.pe.clone())
    m.set_classes([f"object{i}" for i in range(len(pes))], torch.cat(pes, dim=1))
    return timed(lambda: m.predict(bgr, conf=0.001, verbose=False, device=DEV))


def yoloe_text(bgr, weights):
    from ultralytics import YOLOE
    m = YOLOE(str(MODELS / weights))
    m.set_classes(["keys"], m.get_text_pe(["keys"]))
    return timed(lambda: m.predict(bgr, conf=0.001, verbose=False, device=DEV))


def match(frame, bgr, weights, k, conf, text, nref=None):
    """Detector proposes boxes, DINOv2-small compares each crop with the 6 registration crops."""
    from transformers import AutoImageProcessor, AutoModel
    from ultralytics import YOLOE
    det = YOLOE(str(MODELS / weights))
    if text:
        det.set_classes(["keys"], det.get_text_pe(["keys"]))
    proc = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
    enc = AutoModel.from_pretrained("facebook/dinov2-small", use_safetensors=True).to(DEV).eval()

    def emb(crops):
        with torch.no_grad():
            return torch.nn.functional.normalize(enc(**proc(images=crops, return_tensors="pt").to(DEV)).pooler_output, dim=-1)

    ref = emb([reg_crop(rf) for rf in ITEM["reg_order"][:nref]])

    def once():
        r = det.predict(bgr, conf=conf, verbose=False, device=DEV)[0]
        order = r.boxes.conf.argsort(descending=True)[:k].tolist() if len(r.boxes) else []
        boxes = [r.boxes.xyxy[i].tolist() for i in order if (r.boxes.xyxy[i][2] - r.boxes.xyxy[i][0]) > 6]
        if boxes:
            int((emb([frame.crop(tuple(int(v) for v in b)) for b in boxes]) @ ref.T).max(dim=1).values.argmax())
        return len(boxes)

    n = once()
    return timed(once), n


if __name__ == "__main__":
    frame = phone_frame()
    bgr = np.ascontiguousarray(np.array(frame)[:, :, ::-1])
    res = {"device": f"M3 Pro Mac, PyTorch {torch.__version__} on {DEV}, fp32 unless noted", "frame": "1440x1920 portrait",
           "jpeg_q80_kb": {"1920 px long side": jpeg_kb(frame, 1920), "960 px long side": jpeg_kb(frame, 960)}}
    o32, o16 = owlv2(frame), owlv2(frame, torch.float16)
    res["owlv2_fp32"], res["owlv2_fp16"] = o32, o16
    res["owlv2_tflop_per_frame"] = owlv2_tflops(frame)
    ms = {"owlv2_image": o32["img1_ms"], "owlv2_img1_name": o32["img1_name_ms"], "owlv2_text": o32["name_only_ms"],
          "owlv2_img6_name": o32["img6_name_ms"]}
    for size in ("s", "l", "x"):
        ms[f"yoloe26{size}_vp"] = yoloe_vp(bgr, f"yoloe-26{size}-seg.pt", 1)
        ms[f"yoloe26{size}_vp3"] = yoloe_vp(bgr, f"yoloe-26{size}-seg.pt", 3)
    ms["yoloe26l_text"] = yoloe_text(bgr, "yoloe-26l-seg.pt")
    ms["yoloe26x_text"] = yoloe_text(bgr, "yoloe-26x-seg.pt")
    ms["text_then_match1"], n_t = match(frame, bgr, "yoloe-26l-seg.pt", 5, 0.01, True, nref=1)
    ms["propose_match1"], n_p = match(frame, bgr, "yoloe-26s-seg-pf.pt", 40, 0.02, False, nref=1)
    res["per_method_ms"] = ms
    res["crops_matched"] = {"text_then_match1": n_t, "propose_match1": n_p}
    print(json.dumps(res, indent=1), flush=True)
    rep = ROOT / "reports" / "poc22_registered_find.json"
    allr = json.loads(rep.read_text())
    allr["server_mode_latency"] = res
    rep.write_text(json.dumps(allr, indent=2))
