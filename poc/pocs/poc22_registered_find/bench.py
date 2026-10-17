"""POC 22: "These are my keys" -> find them later. Which approach finds a REGISTERED item best, and fast?

Data: ORBIT (Microsoft/City Univ. London): blind and low-vision users filmed their own objects.
Registration = frames from the item's clean videos (box from Apple Vision's foreground mask).
Test = the user's cluttered videos, with a human-drawn box on the target (ORBIT annotations).
18 items: keys x4, remotes x2, wallets x2, sunglasses x2, phones x2, watches x2, headphones x2, cane, purse.

Methods
  yoloe26s_vp / yoloe26l_vp   YOLOE visual prompt, cross-image: box on the registration photo -> find in frame
  *_vp3                       same, 3 registration photos, best-scoring answer kept
  owlv2_image                 OWLv2 image-guided one-shot detection with the registration crop
  propose_match               Option A: YOLOE prompt-free boxes everything -> DINOv2 embeddings of each
                              box vs the 6 registration crops -> best match
  yoloe26l_text               text prompt with the item's name (baseline)
Metric: top-1 box overlaps the human box (IoU >= 0.5, and >= 0.3). Frames where the item fills >60 % of
the view are dropped (too easy).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "downloads" / "orbit_frames"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
NAMES = {"keys": "keys", "door-keys": "keys", "front-door-keys": "keys", "apple-tv-remote": "remote control",
         "remote-control": "remote control", "wallet": "wallet", "sunglasses": "sunglasses", "apple-mobile-phone": "phone",
         "iphone-6": "phone", "wrist-watch": "wrist watch", "apple-watch": "smart watch", "bose-wireless-headphones": "headphones",
         "headphones": "headphones", "cane": "white cane", "ladies-purse": "purse"}


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


def items():
    out = []
    for d in sorted(DATA.glob("P*--*")):
        reg = json.loads((d / "register" / "boxes.json").read_text())
        tb = d / "register" / "boxes_text.json"
        if tb.exists():
            txt = json.loads(tb.read_text())
            reg = {f: txt.get(f, b) for f, b in reg.items()}
            reg_order = [f for f in sorted(reg) if f in txt] + [f for f in sorted(reg) if f not in txt]
        else:
            reg_order = sorted(reg)
        tests = []
        for e in json.loads((d / "test.json").read_text()):
            x, y, w, h = [v * 224 / 1080 for v in e["box_xywh"]]
            if w * h > 0.6 * 224 * 224:
                continue
            tests.append((str(d / e["file"]), [x, y, x + w, y + h]))
        out.append(dict(name=d.name, obj=d.name.split("--")[1], reg=reg, reg_order=reg_order, regdir=d / "register", tests=tests))
    return out


def run_yoloe_vp(weights, its, nref=1):
    from ultralytics import YOLOE
    m = YOLOE(weights)
    res, times = [], []
    for it in its:
        refs = it["reg_order"][:nref]
        for path, gt in it["tests"]:
            best = (None, -1)
            for rf in refs:
                t0 = time.time()
                r = m.predict(path, refer_image=str(it["regdir"] / rf), visual_prompts={"bboxes": np.array([it["reg"][rf]]), "cls": np.array([0])},
                              conf=0.001, verbose=False, device=DEV)[0]
                times.append(time.time() - t0)
                if len(r.boxes):
                    k = int(r.boxes.conf.argmax()); c = float(r.boxes.conf[k])
                    if c > best[1]:
                        best = (r.boxes.xyxy[k].tolist(), c)
            res.append((it["name"], best[0], gt))
    return res, times


def run_yoloe_vp_cached(weights, its, nref=1, fusion="any"):
    """Same answers as run_yoloe_vp, but each registration photo is encoded once per item, as a server would:
    the photo embeddings become the model's classes (one per photo) and every test frame is a plain predict.
    fusion any: one class per photo, the best-scoring box over all photos wins; mean: one class whose embedding
    is the average of the photo embeddings."""
    from ultralytics import YOLOE
    m = YOLOE(weights)
    res, times = [], []
    for it in its:
        pes = []
        for rf in it["reg_order"][:nref]:
            m.predict(it["tests"][0][0], refer_image=str(it["regdir"] / rf), visual_prompts={"bboxes": np.array([it["reg"][rf]]), "cls": np.array([0])},
                      conf=0.001, verbose=False, device=DEV)
            pes.append(m.model.pe.clone())
        pe = torch.cat(pes, dim=1)
        if fusion == "mean":
            pe = torch.nn.functional.normalize(torch.nn.functional.normalize(pe, dim=-1).mean(dim=1, keepdim=True), dim=-1)
        m.set_classes([f"object{i}" for i in range(pe.shape[1])], pe)
        for path, gt in it["tests"]:
            t0 = time.time()
            r = m.predict(path, conf=0.001, verbose=False, device=DEV)[0]
            times.append(time.time() - t0)
            box = r.boxes.xyxy[int(r.boxes.conf.argmax())].tolist() if len(r.boxes) else None
            res.append((it["name"], box, gt))
    return res, times


def run_owlv2_cached(its, nref=1, with_name=False, name_only=False, fusion="max"):
    """OWLv2 with each registration photo encoded once (one query embedding per photo; the best-scoring box
    over all photos wins). Top box = argmax of the logits, which is what post-processing + NMS returns first.
    with_name: add the logit of the item's name as a text query, so a box must look like the photos AND be
    that kind of thing. name_only: the name as a text query, no photos.
    fusion over photos: max (any photo matches), mean (average logit: all photos must roughly agree) or
    proto (one query = the mean of the photo embeddings)."""
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained("google/owlv2-base-patch16-ensemble")
    model = Owlv2ForObjectDetection.from_pretrained("google/owlv2-base-patch16-ensemble", use_safetensors=True).to(DEV).eval()
    res, times = [], []
    for it in its:
        name = NAMES.get(it["obj"], it["obj"].replace("-", " "))
        with torch.no_grad():
            q = []
            for rf in [] if name_only else it["reg_order"][:nref]:
                crop = Image.open(it["regdir"] / rf).convert("RGB").crop(tuple(int(v) for v in it["reg"][rf]))
                qmap = model.image_embedder(pixel_values=proc(images=crop, return_tensors="pt")["pixel_values"].to(DEV))[0]
                q.append(model.embed_image_query(qmap.reshape(1, -1, qmap.shape[-1]), qmap)[0])
            tok = proc(text=[[f"a photo of {name}"]], return_tensors="pt").to(DEV)
            temb = model.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[:, None, :]
        for path, gt in it["tests"]:
            im = Image.open(path).convert("RGB")
            t0 = time.time()
            with torch.no_grad():
                fmap = model.image_embedder(pixel_values=proc(images=im, return_tensors="pt")["pixel_values"].to(DEV))[0]
                feats = fmap.reshape(1, -1, fmap.shape[-1])
                if name_only:
                    s = model.class_predictor(image_feats=feats, query_embeds=temb)[0][0, :, 0]
                elif fusion == "proto":
                    proto = torch.nn.functional.normalize(torch.cat(q, dim=1), dim=-1).mean(dim=1, keepdim=True)
                    s = model.class_predictor(image_feats=feats, query_embeds=proto)[0][0, :, 0]
                else:
                    lg = model.class_predictor(image_feats=feats, query_embeds=torch.cat(q, dim=1))[0][0]
                    s = lg.max(dim=-1).values if fusion == "max" else lg.mean(dim=-1)
                if with_name:
                    s = s + model.class_predictor(image_feats=feats, query_embeds=temb)[0][0, :, 0]
                cx, cy, w, h = model.box_predictor(feats, fmap)[0, int(s.argmax())].tolist()
            times.append(time.time() - t0)
            side = max(im.size)  # OWLv2 pads to a square at the bottom/right; boxes are fractions of that square
            res.append((it["name"], [(cx - w / 2) * side, (cy - h / 2) * side, (cx + w / 2) * side, (cy + h / 2) * side], gt))
    return res, times


def run_yoloe_text(weights, its):
    from ultralytics import YOLOE
    m = YOLOE(weights)
    res, times = [], []
    for it in its:
        name = NAMES.get(it["obj"], it["obj"].replace("-", " "))
        try:
            m.set_classes([name], m.get_text_pe([name]))
        except Exception:
            m.set_classes([name])
        for path, gt in it["tests"]:
            t0 = time.time()
            r = m.predict(path, conf=0.001, verbose=False, device=DEV)[0]
            times.append(time.time() - t0)
            box = r.boxes.xyxy[int(r.boxes.conf.argmax())].tolist() if len(r.boxes) else None
            res.append((it["name"], box, gt))
    return res, times


def run_owlv2(its):
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained("google/owlv2-base-patch16-ensemble")
    model = Owlv2ForObjectDetection.from_pretrained("google/owlv2-base-patch16-ensemble", use_safetensors=True).to(DEV).eval()
    res, times = [], []
    for it in its:
        rf = it["reg_order"][0]
        q = Image.open(it["regdir"] / rf).convert("RGB").crop(tuple(int(v) for v in it["reg"][rf]))
        for path, gt in it["tests"]:
            im = Image.open(path).convert("RGB")
            t0 = time.time()
            inputs = proc(images=im, query_images=q, return_tensors="pt").to(DEV)
            with torch.no_grad():
                out = model.image_guided_detection(**inputs)
            # OWLv2 pads to a square; our frames are square already (224 x 224)
            r = proc.post_process_image_guided_detection(outputs=out, threshold=0.0, nms_threshold=0.3, target_sizes=torch.tensor([[im.height, im.width]]))[0]
            times.append(time.time() - t0)
            box = r["boxes"][int(r["scores"].argmax())].tolist() if len(r["scores"]) else None
            res.append((it["name"], box, gt))
    return res, times


def run_propose_match(its, nref=None):
    from transformers import AutoImageProcessor, AutoModel
    from ultralytics import YOLOE
    det = YOLOE("yoloe-26s-seg-pf.pt")
    proc = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
    enc = AutoModel.from_pretrained("facebook/dinov2-small", use_safetensors=True).to(DEV).eval()

    def emb(crops):
        with torch.no_grad():
            x = proc(images=crops, return_tensors="pt").to(DEV)
            e = enc(**x).pooler_output
        return torch.nn.functional.normalize(e, dim=-1)

    res, times = [], []
    for it in its:
        crops = [Image.open(it["regdir"] / f).convert("RGB").crop(tuple(int(v) for v in it["reg"][f]))
                 for f in (sorted(it["reg"]) if nref is None else it["reg_order"][:nref])]
        ref = emb(crops)
        for path, gt in it["tests"]:
            im = Image.open(path).convert("RGB")
            t0 = time.time()
            r = det.predict(path, conf=0.02, verbose=False, device=DEV)[0]
            boxes = [b for b in r.boxes.xyxy.tolist() if (b[2] - b[0]) > 8 and (b[3] - b[1]) > 8][:40]
            if not boxes:
                times.append(time.time() - t0); res.append((it["name"], None, gt)); continue
            e = emb([im.crop(tuple(int(v) for v in b)) for b in boxes])
            score = (e @ ref.T).max(dim=1).values
            times.append(time.time() - t0)
            res.append((it["name"], boxes[int(score.argmax())], gt))
    return res, times


CATEGORY = {"keys": "keys", "door-keys": "keys", "front-door-keys": "keys", "apple-tv-remote": "remote", "remote-control": "remote",
            "wallet": "wallet", "ladies-purse": "wallet", "sunglasses": "sunglasses", "apple-mobile-phone": "phone", "iphone-6": "phone",
            "wrist-watch": "watch", "apple-watch": "watch", "bose-wireless-headphones": "headphones", "headphones": "headphones", "cane": "remote"}


def mosaic_items(its, seed=0):
    """2x2 mosaic per test frame: the user's own cluttered frame + 3 frames of OTHER users' look-alike items."""
    import random
    rng = random.Random(seed)
    out_dir = ROOT / "data" / "tmp" / "mosaics"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_cat = {}
    for it in its:
        by_cat.setdefault(CATEGORY.get(it["obj"], it["obj"]), []).append(it)
    mos = []
    for it in its:
        peers = [p for p in by_cat[CATEGORY.get(it["obj"], it["obj"])] if p["name"].split("--")[0] != it["name"].split("--")[0]]
        pool = [t for p in peers for t in p["tests"]] or [t for p in its if p is not it for t in p["tests"]]
        tests = []
        for k, (path, gt) in enumerate(it["tests"]):
            others = [rng.choice(pool)[0] for _ in range(3)]
            slot = rng.randrange(4)
            tiles = others[:slot] + [path] + others[slot:]
            canvas = Image.new("RGB", (448, 448))
            for i, tp in enumerate(tiles):
                canvas.paste(Image.open(tp).convert("RGB").resize((224, 224)), ((i % 2) * 224, (i // 2) * 224))
            ox, oy = (slot % 2) * 224, (slot // 2) * 224
            f = out_dir / f"{it['name']}_{k:02d}.jpg"
            canvas.save(f, quality=92)
            tests.append((str(f), [gt[0] + ox, gt[1] + oy, gt[2] + ox, gt[3] + oy]))
        mos.append({**it, "tests": tests})
    return mos


def run_text_match(its, k=5, nref=None):
    """Two-stage: text prompt proposes the right KIND of object (top-k boxes), DINOv2 picks YOURS."""
    from transformers import AutoImageProcessor, AutoModel
    from ultralytics import YOLOE
    det = YOLOE("yoloe-26l-seg.pt")
    proc = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
    enc = AutoModel.from_pretrained("facebook/dinov2-small", use_safetensors=True).to(DEV).eval()

    def emb(crops):
        with torch.no_grad():
            e = enc(**proc(images=crops, return_tensors="pt").to(DEV)).pooler_output
        return torch.nn.functional.normalize(e, dim=-1)

    res, times = [], []
    for it in its:
        name = NAMES.get(it["obj"], it["obj"].replace("-", " "))
        try:
            det.set_classes([name], det.get_text_pe([name]))
        except Exception:
            det.set_classes([name])
        ref = emb([Image.open(it["regdir"] / f).convert("RGB").crop(tuple(int(v) for v in it["reg"][f])) for f in it["reg_order"][:nref]])
        for path, gt in it["tests"]:
            im = Image.open(path).convert("RGB")
            t0 = time.time()
            r = det.predict(path, conf=0.01, verbose=False, device=DEV)[0]
            order = r.boxes.conf.argsort(descending=True)[:k].tolist() if len(r.boxes) else []
            boxes = [r.boxes.xyxy[i].tolist() for i in order if (r.boxes.xyxy[i][2] - r.boxes.xyxy[i][0]) > 6]
            if not boxes:
                times.append(time.time() - t0); res.append((it["name"], None, gt)); continue
            sim = (emb([im.crop(tuple(int(v) for v in b)) for b in boxes]) @ ref.T).max(dim=1).values
            times.append(time.time() - t0)
            res.append((it["name"], boxes[int(sim.argmax())], gt))
    return res, times


def score(res):
    h5 = [b is not None and iou(b, g) >= 0.5 for _, b, g in res]
    h3 = [b is not None and iou(b, g) >= 0.3 for _, b, g in res]
    per = {}
    for (n, b, g), ok in zip(res, h5):
        per.setdefault(n, []).append(ok)
    return float(np.mean(h5)), float(np.mean(h3)), {k: round(float(np.mean(v)), 2) for k, v in per.items()}


if __name__ == "__main__":
    its = items()
    task = "own_clutter"
    if "--lookalikes" in sys.argv:
        sys.argv.remove("--lookalikes")
        its = mosaic_items(its)
        task = "lookalikes"
    print(f"{len(its)} items, {sum(len(i['tests']) for i in its)} test frames (item fills <60 % of view)")
    methods = {
        "yoloe26s_vp": lambda: run_yoloe_vp("yoloe-26s-seg.pt", its),
        "yoloe26l_vp": lambda: run_yoloe_vp("yoloe-26l-seg.pt", its),
        "yoloe26s_vp3": lambda: run_yoloe_vp("yoloe-26s-seg.pt", its, nref=3),
        "owlv2_image": lambda: run_owlv2(its),
        "propose_match": lambda: run_propose_match(its),
        "yoloe26l_text": lambda: run_yoloe_text("yoloe-26l-seg.pt", its),
        "text_then_match": lambda: run_text_match(its),
        # registration encoded once per item (deployment mode); *_check must reproduce the rows above
        "owlv2_img1_check": lambda: run_owlv2_cached(its, 1),
        "owlv2_img3": lambda: run_owlv2_cached(its, 3),
        "owlv2_img6": lambda: run_owlv2_cached(its, 6),
        "owlv2_img6_name": lambda: run_owlv2_cached(its, 6, with_name=True),
        "owlv2_text": lambda: run_owlv2_cached(its, name_only=True),
        "owlv2_img1_name": lambda: run_owlv2_cached(its, 1, with_name=True),
        "owlv2_img3_mean": lambda: run_owlv2_cached(its, 3, fusion="mean"),
        "owlv2_img6_mean": lambda: run_owlv2_cached(its, 6, fusion="mean"),
        "owlv2_img3_proto": lambda: run_owlv2_cached(its, 3, fusion="proto"),
        "owlv2_img6_proto": lambda: run_owlv2_cached(its, 6, fusion="proto"),
        "owlv2_img3_mean_name": lambda: run_owlv2_cached(its, 3, with_name=True, fusion="mean"),
        "owlv2_img6_mean_name": lambda: run_owlv2_cached(its, 6, with_name=True, fusion="mean"),
        "yoloe26l_vp_check": lambda: run_yoloe_vp_cached("yoloe-26l-seg.pt", its),
        "yoloe26l_vp3": lambda: run_yoloe_vp_cached("yoloe-26l-seg.pt", its, 3),
        "yoloe26x_vp": lambda: run_yoloe_vp_cached("yoloe-26x-seg.pt", its),
        "yoloe26x_vp3": lambda: run_yoloe_vp_cached("yoloe-26x-seg.pt", its, 3),
        "yoloe26x_text": lambda: run_yoloe_text("yoloe-26x-seg.pt", its),
        "text_then_match1": lambda: run_text_match(its, nref=1),
        "propose_match1": lambda: run_propose_match(its, nref=1),
        "yoloe26x_vp6_mean": lambda: run_yoloe_vp_cached("yoloe-26x-seg.pt", its, 6, fusion="mean"),
        "yoloe26l_vp6_mean": lambda: run_yoloe_vp_cached("yoloe-26l-seg.pt", its, 6, fusion="mean"),
        "yoloe26x_vp3_mean": lambda: run_yoloe_vp_cached("yoloe-26x-seg.pt", its, 3, fusion="mean"),
    }
    only = sys.argv[1:] or list(methods)
    out = {}
    for name in only:
        res, times = methods[name]()
        h5, h3, per = score(res)
        out[name] = dict(hit_iou50_pct=round(100 * h5, 1), hit_iou30_pct=round(100 * h3, 1),
                         median_s_per_frame=round(float(np.median(times[1:])), 3) if len(times) > 1 else None, per_item=per)
        print(f"{name:15} top-1 correct: {100 * h5:5.1f}% (IoU>=0.5)  {100 * h3:5.1f}% (IoU>=0.3)  median {out[name]['median_s_per_frame']} s/frame on this Mac", flush=True)
    prev = ROOT / "reports" / "poc22_registered_find.json"
    old = json.loads(prev.read_text()) if prev.exists() else {}
    old.setdefault(task, {}).update(out)
    prev.write_text(json.dumps(old, indent=2))
