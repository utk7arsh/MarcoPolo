"""POC 25: two questions the deployed server must answer that the benchmark (POC 22) never asked.

A. "Is MY item in this frame at all?" Most camera frames do not contain your keys. OWLv2 always returns a
   best box, so the server needs a score threshold. We score every ORBIT test frame against every item's
   one-photo registration:
     present   = the item's own cluttered frames (156)
     absent    = frames from OTHER users (so the item cannot be in them), split into
                 look-alike (same category, e.g. someone else's keys) and other category
   Report ROC AUC and the true-positive rate at 1 / 5 / 10 % false positives, plus the threshold.
B. "Is this registration photo good enough, or should we ask for a retake?" For every registration photo
   (6 per item) compare cheap signals (OWLv2's own score for the item's name in the photo, sharpness,
   how much of the photo the item fills) with how well that photo later finds the item
   (per-photo accuracy from registration_study.py).
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("poc22_bench", ROOT / "pocs" / "poc22_registered_find" / "bench.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
OWL = "google/owlv2-base-patch16-ensemble"


def roc(pos, neg):
    pos, neg = np.asarray(pos), np.asarray(neg)
    auc = float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())
    out = {"auc": round(auc, 3)}
    for fpr in (0.01, 0.05, 0.10):
        thr = float(np.quantile(neg, 1 - fpr))
        out[f"tpr_at_{int(fpr * 100)}pct_fp"] = round(float((pos > thr).mean()) * 100, 1)
        out[f"threshold_at_{int(fpr * 100)}pct_fp"] = round(thr, 3)
    return out


def sharpness(im):
    g = np.asarray(im.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    return float(g.var())


def main():
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL)
    model = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True).to(B.DEV).eval()
    its = B.items()
    names = [B.NAMES.get(it["obj"], it["obj"].replace("-", " ")) for it in its]
    users = [it["name"].split("--")[0] for it in its]
    cats = [B.CATEGORY.get(it["obj"], it["obj"]) for it in its]

    def image_pass(im):
        fmap = model.image_embedder(pixel_values=proc(images=im, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
        return fmap, fmap.reshape(1, -1, fmap.shape[-1])

    with torch.no_grad():
        Q = []
        for it in its:  # one-photo registration: the first photo the name detector boxed
            rf = it["reg_order"][0]
            crop = Image.open(it["regdir"] / rf).convert("RGB").crop(tuple(int(v) for v in it["reg"][rf]))
            fmap, feats = image_pass(crop)
            Q.append(model.embed_image_query(feats, fmap)[0])
        Q = torch.cat(Q, dim=1)                                           # (1, 18, 512)
        tok = proc(text=[[f"a photo of {n}" for n in names]], return_tensors="pt").to(B.DEV)
        T = model.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[None]

    # ---------------- A. presence
    frames = [(i, path, gt) for i, it in enumerate(its) for path, gt in it["tests"]]
    S = np.zeros((len(frames), len(its)))          # max sigmoid score of item q's query in frame f
    HIT = np.zeros((len(frames), len(its)), bool)  # top box of query q overlaps the frame's GT (only meaningful for q == owner)
    with torch.no_grad():
        for f, (owner, path, gt) in enumerate(frames):
            im = Image.open(path).convert("RGB")
            fmap, feats = image_pass(im)
            logits = model.class_predictor(image_feats=feats, query_embeds=Q)[0][0]          # (patches, 18)
            boxes = model.box_predictor(feats, fmap)[0].cpu().numpy()
            S[f] = torch.sigmoid(logits).max(dim=0).values.cpu().numpy()
            side = max(im.size)
            for q in range(len(its)):
                cx, cy, w, h = boxes[int(logits[:, q].argmax())]
                HIT[f, q] = B.iou([(cx - w / 2) * side, (cy - h / 2) * side, (cx + w / 2) * side, (cy + h / 2) * side], gt) >= 0.5
    pos, pos_hit, neg_look, neg_other = [], [], [], []
    for f, (owner, _, _) in enumerate(frames):
        for q in range(len(its)):
            if q == owner:
                pos.append(S[f, q]); pos_hit.append(HIT[f, q])
            elif users[frames[f][0]] != users[q]:
                (neg_look if cats[frames[f][0]] == cats[q] else neg_other).append(S[f, q])
    pres = {
        "n_present": len(pos), "n_absent_lookalike": len(neg_look), "n_absent_other": len(neg_other),
        "present_score_median": round(float(np.median(pos)), 3),
        "absent_lookalike_score_median": round(float(np.median(neg_look)), 3),
        "absent_other_score_median": round(float(np.median(neg_other)), 3),
        "vs_other_category": roc(pos, neg_other),
        "vs_lookalikes": roc(pos, neg_look),
        "vs_all_absent": roc(pos, neg_look + neg_other),
    }
    # Correct AND confident: of present frames, how many pass the 5 % threshold with the right box?
    thr5 = pres["vs_all_absent"]["threshold_at_5pct_fp"]
    pres["present_frames_passing_5pct_threshold_with_correct_box_pct"] = round(100 * float(np.mean([s > thr5 and h for s, h in zip(pos, pos_hit)])), 1)
    print(json.dumps(pres, indent=1), flush=True)

    # ---------------- B. registration retake gate
    study = json.loads((ROOT / "reports" / "poc22_registration_study.json").read_text())["per_item"]
    rows = []
    with torch.no_grad():
        for i, it in enumerate(its):
            for k, rf in enumerate(it["reg_order"]):
                im = Image.open(it["regdir"] / rf).convert("RGB")
                fmap, feats = image_pass(im)
                tl = model.class_predictor(image_feats=feats, query_embeds=T[:, i:i + 1, :])[0][0, :, 0]
                score = float(torch.sigmoid(tl).max())
                box = it["reg"][rf]
                crop = im.crop(tuple(int(v) for v in box))
                rows.append(dict(item=it["name"], photo=k + 1, name_score=score, sharpness=sharpness(crop),
                                 fill=(box[2] - box[0]) * (box[3] - box[1]) / (im.width * im.height),
                                 acc_own=study["own_clutter"][f"photo {k + 1}"][it["name"]],
                                 acc_look=study["lookalikes"][f"photo {k + 1}"][it["name"]]))
    good = np.array([r["acc_own"] >= 0.8 for r in rows])
    gate = {"n_photos": len(rows), "good_photos_pct": round(100 * float(good.mean()), 1)}
    for sig in ("name_score", "sharpness", "fill"):
        v = np.array([r[sig] for r in rows])
        gate[f"auc_{sig}_predicts_good_photo"] = roc(v[good], v[~good])["auc"]
    v = np.array([r["name_score"] for r in rows])
    acc = np.array([r["acc_own"] for r in rows]); accl = np.array([r["acc_look"] for r in rows])
    sweep = {}
    for thr in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5):
        keep = v >= thr
        if keep.any() and (~keep).any():
            sweep[f"name_score >= {thr}"] = dict(retake_pct=round(100 * float((~keep).mean()), 1),
                                                 kept_acc_own=round(100 * float(acc[keep].mean()), 1),
                                                 rejected_acc_own=round(100 * float(acc[~keep].mean()), 1),
                                                 kept_acc_lookalike=round(100 * float(accl[keep].mean()), 1))
    gate["name_score_sweep"] = sweep
    gate["all_photos_acc_own"] = round(100 * float(acc.mean()), 1)
    print(json.dumps(gate, indent=1), flush=True)
    (ROOT / "reports" / "poc25_presence_gate.json").write_text(json.dumps({"presence": pres, "registration_gate": gate, "photos": rows}, indent=2))


if __name__ == "__main__":
    main()
