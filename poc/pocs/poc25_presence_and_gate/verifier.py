"""POC 25c: does a second opinion on OWLv2's best box fix the look-alike false positives?

For every (frame, registered item) pair: OWLv2's best box for that item; DINOv2-small compares the box's
crop with the item's registration crop (same instance or not?). Presence scores compared:
  photo + name          image-guided logit + name logit at the best box (best of POC 25b on other objects)
  vs my others          best box looks more like this item than like my other registered items
  DINOv2 check          cosine similarity of the box crop with the registration crop
  photo + name + DINOv2, and all four (standardised sums)
One frame, and two frames of the same scene that must both pass.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("poc25", HERE / "run.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
B, OWL, roc = R.B, R.OWL, R.roc


def main():
    from transformers import AutoImageProcessor, AutoModel, Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL)
    model = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True).to(B.DEV).eval()
    dproc = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
    dino = AutoModel.from_pretrained("facebook/dinov2-small", use_safetensors=True).to(B.DEV).eval()

    def demb(crops):
        with torch.no_grad():
            return torch.nn.functional.normalize(dino(**dproc(images=crops, return_tensors="pt").to(B.DEV)).pooler_output, dim=-1)

    its = B.items()
    names = [B.NAMES.get(it["obj"], it["obj"].replace("-", " ")) for it in its]
    users = [it["name"].split("--")[0] for it in its]
    cats = [B.CATEGORY.get(it["obj"], it["obj"]) for it in its]
    reg_crops = []
    with torch.no_grad():
        Q = []
        for it in its:
            rf = it["reg_order"][0]
            crop = Image.open(it["regdir"] / rf).convert("RGB").crop(tuple(int(v) for v in it["reg"][rf]))
            reg_crops.append(crop)
            fmap = model.image_embedder(pixel_values=proc(images=crop, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
            Q.append(model.embed_image_query(fmap.reshape(1, -1, fmap.shape[-1]), fmap)[0])
        Q = torch.cat(Q, dim=1)
        tok = proc(text=[[f"a photo of {n}" for n in names]], return_tensors="pt").to(B.DEV)
        Tq = model.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[None]
    REF = demb(reg_crops)                                                     # (items, d)

    frames = [(i, path) for i, it in enumerate(its) for path, _ in it["tests"]]
    S = {k: np.zeros((len(frames), len(its))) for k in ("photo + name", "vs my others", "DINOv2 check")}
    with torch.no_grad():
        for f, (_, path) in enumerate(frames):
            im = Image.open(path).convert("RGB")
            fmap = model.image_embedder(pixel_values=proc(images=im, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
            feats = fmap.reshape(1, -1, fmap.shape[-1])
            L = model.class_predictor(image_feats=feats, query_embeds=Q)[0][0].cpu().numpy()
            Lt = model.class_predictor(image_feats=feats, query_embeds=Tq)[0][0].cpu().numpy()
            boxes = model.box_predictor(feats, fmap)[0].cpu().numpy()
            side = max(im.size)
            best = L.argmax(0)
            crops = []
            for q in range(len(its)):
                b = best[q]
                S["photo + name"][f, q] = L[b, q] + Lt[b, q]
                S["vs my others"][f, q] = L[b, q] - np.delete(L[b], q).max()
                cx, cy, w, h = boxes[b]
                x0, y0 = max(0, (cx - w / 2) * side), max(0, (cy - h / 2) * side)
                x1, y1 = min(im.width, (cx + w / 2) * side), min(im.height, (cy + h / 2) * side)
                crops.append(im.crop((int(x0), int(y0), max(int(x1), int(x0) + 4), max(int(y1), int(y0) + 4))))
            E = demb(crops)                                                   # (items, d), crop for each query
            S["DINOv2 check"][f] = (E * REF).sum(-1).cpu().numpy()
    z = lambda a: (a - a.mean()) / (a.std() + 1e-9)
    S["photo + name + DINOv2"] = z(S["photo + name"]) + z(S["DINOv2 check"])
    S["all four"] = z(S["photo + name"]) + z(S["vs my others"]) + z(S["DINOv2 check"])

    vid = {}
    for f, (owner, _) in enumerate(frames):
        vid.setdefault(owner, []).append(f)
    rng = np.random.default_rng(0)
    out = {}
    for name, M in S.items():
        pos, look, other, pos2, look2, other2 = [], [], [], [], [], []
        for f, (owner, _) in enumerate(frames):
            for q in range(len(its)):
                if q == owner:
                    pos.append(M[f, q])
                elif users[owner] != users[q]:
                    (look if cats[owner] == cats[q] else other).append(M[f, q])
        for owner, fs in vid.items():
            for _ in range(10):
                a, b = rng.choice(fs, 2, replace=False)
                for q in range(len(its)):
                    s2 = min(M[a, q], M[b, q])
                    if q == owner:
                        pos2.append(s2)
                    elif users[owner] != users[q]:
                        (look2 if cats[owner] == cats[q] else other2).append(s2)
        out[name] = {"one frame": {"vs other category": roc(pos, other), "vs look-alikes": roc(pos, look)},
                     "two frames agree": {"vs other category": roc(pos2, other2), "vs look-alikes": roc(pos2, look2)}}
        o, t2 = out[name]["one frame"], out[name]["two frames agree"]
        print(f"{name:22} AUC {o['vs other category']['auc']:.3f} / look-alike {o['vs look-alikes']['auc']:.3f} | caught at 1% false: one frame "
              f"{o['vs other category']['tpr_at_1pct_fp']:5.1f}% / {o['vs look-alikes']['tpr_at_1pct_fp']:5.1f}%, two frames "
              f"{t2['vs other category']['tpr_at_1pct_fp']:5.1f}% / {t2['vs look-alikes']['tpr_at_1pct_fp']:5.1f}%", flush=True)
    rep = ROOT / "reports" / "poc25_presence_gate.json"
    allr = json.loads(rep.read_text())
    allr["presence_verifier"] = out
    rep.write_text(json.dumps(allr, indent=2))


if __name__ == "__main__":
    main()
