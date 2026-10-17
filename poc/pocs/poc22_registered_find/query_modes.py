"""POC 22 add-on: one-shot registration with OWLv2: which part of the registration photo becomes the query?

transformers 5.x picks, inside the registration crop, the region OWLv2 finds most object-like (it can be one
key or the fob instead of the whole bunch). Two standard alternatives:
  whole crop     older transformers rule: among regions covering most of the crop (IoU >= 0.8 x best with the
                 crop), take the most distinctive one (least similar to the crop's mean embedding)
  box in photo   official OWL-ViT recipe: run the FULL registration photo and take the predicted region that
                 best overlaps the registration box (the model sees the item in context)
Scored per single photo (every one of the 6), plus the first photo the name detector boxed, both tasks.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("poc22_bench", HERE / "bench.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
OWL = "google/owlv2-base-patch16-ensemble"


def corners(b):
    cx, cy, w, h = b.unbind(-1)
    return torch.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], -1)


def iou_many(ref, boxes):
    ix = (torch.minimum(ref[2], boxes[:, 2]) - torch.maximum(ref[0], boxes[:, 0])).clamp(min=0)
    iy = (torch.minimum(ref[3], boxes[:, 3]) - torch.maximum(ref[1], boxes[:, 1])).clamp(min=0)
    inter = ix * iy
    area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / ((ref[2] - ref[0]) * (ref[3] - ref[1]) + area - inter + 1e-9)


def main():
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL)
    model = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True).to(B.DEV).eval()

    def embed(im):
        fmap = model.image_embedder(pixel_values=proc(images=im, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
        feats = fmap.reshape(1, -1, fmap.shape[-1])
        cls = model.class_predictor(feats)[1][0]                       # (patches, 512) class embeddings
        return feats, fmap, cls, corners(model.box_predictor(feats, fmap)[0])

    def queries(it, rf):
        im = Image.open(it["regdir"] / rf).convert("RGB")
        box = it["reg"][rf]
        crop = im.crop(tuple(int(v) for v in box))
        out = {}
        with torch.no_grad():
            feats, fmap, cls, bx = embed(crop)
            out["objectness in crop"] = model.embed_image_query(feats, fmap)[0][0, 0]
            side = max(crop.size)
            ious = iou_many(torch.tensor([0, 0, crop.width / side, crop.height / side], device=B.DEV), bx)
            sel = (ious >= 0.8 * ious.max()).nonzero().squeeze(1)
            mean_sim = cls[sel] @ cls.mean(dim=0)
            out["whole crop"] = cls[sel[int(mean_sim.argmin())]]
            feats, fmap, cls, bx = embed(im)
            side = max(im.size)
            ref = torch.tensor([v / side for v in box], device=B.DEV)
            out["box in photo"] = cls[int(iou_many(ref, bx).argmax())]
        return out

    base = B.items()
    res = {}
    for task, its in (("own_clutter", base), ("lookalikes", B.mosaic_items(base))):
        hits = {}
        for it in its:
            named = json.loads((it["regdir"] / "boxes_text.json").read_text()) if (it["regdir"] / "boxes_text.json").exists() else {}
            first_named = next((k for k, f in enumerate(it["reg_order"]) if f in named), 0)
            Q = [queries(it, rf) for rf in it["reg_order"]]
            modes = list(Q[0])
            for path, gt in it["tests"]:
                im = Image.open(path).convert("RGB")
                with torch.no_grad():
                    fmap = model.image_embedder(pixel_values=proc(images=im, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
                    feats = fmap.reshape(1, -1, fmap.shape[-1])
                    boxes = model.box_predictor(feats, fmap)[0].cpu().numpy()
                    side = max(im.size)
                    for mode in modes:
                        qe = torch.stack([q[mode] for q in Q])[None]           # (1, n_photos, 512)
                        L = model.class_predictor(image_feats=feats, query_embeds=qe)[0][0]
                        variants = {f"photo {k + 1}": L[:, k] for k in range(L.shape[1])}
                        variants["first named photo"] = L[:, first_named]
                        for k, s in variants.items():
                            cx, cy, w, h = boxes[int(s.argmax())]
                            ok = B.iou([(cx - w / 2) * side, (cy - h / 2) * side, (cx + w / 2) * side, (cy + h / 2) * side], gt) >= 0.5
                            hits.setdefault(mode, {}).setdefault(k, []).append(bool(ok))
        res[task] = {}
        for mode, d in hits.items():
            singles = [float(np.mean(v)) for k, v in d.items() if k.startswith("photo ")]
            res[task][mode] = {"first named photo": round(100 * float(np.mean(d["first named photo"])), 1),
                               "average single photo": round(100 * float(np.mean(singles)), 1),
                               "worst photo slot": round(100 * min(singles), 1),
                               "per photo slot": [round(100 * s, 1) for s in singles]}
            print(task, mode, res[task][mode], flush=True)
    (ROOT / "reports" / "poc22_query_modes.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
