"""POC 25b: can the server tell "my item is in this frame" reliably? Raw OWLv2 scores could not (run.py).

Same frames, same one-photo registrations. Candidate presence scores, all computed from one image pass:
  raw            max image-guided logit over the frame's patches
  frame-relative raw minus the frame's median patch logit (is this patch special in this frame?)
  vs my others   at the best patch: my item's logit minus the best logit of my OTHER registered items
                 (does that box look more like my keys than like my wallet?)
  photo + name   at the best patch: image-guided logit + the logit for the item's name
  all three      frame-relative + vs-my-others + name, each standardised
Plus "two frames agree": both of two frames of the same scene pass the threshold (the server sees 1
frame a second, and the memory can wait for a second sighting before it moves an item).
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
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL)
    model = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True).to(B.DEV).eval()
    its = B.items()
    names = [B.NAMES.get(it["obj"], it["obj"].replace("-", " ")) for it in its]
    users = [it["name"].split("--")[0] for it in its]
    cats = [B.CATEGORY.get(it["obj"], it["obj"]) for it in its]
    with torch.no_grad():
        Q = []
        for it in its:
            rf = it["reg_order"][0]
            crop = Image.open(it["regdir"] / rf).convert("RGB").crop(tuple(int(v) for v in it["reg"][rf]))
            fmap = model.image_embedder(pixel_values=proc(images=crop, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
            Q.append(model.embed_image_query(fmap.reshape(1, -1, fmap.shape[-1]), fmap)[0])
        Q = torch.cat(Q, dim=1)
        tok = proc(text=[[f"a photo of {n}" for n in names]], return_tensors="pt").to(B.DEV)
        Tq = model.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[None]

    frames = [(i, path) for i, it in enumerate(its) for path, _ in it["tests"]]
    scores = {k: np.zeros((len(frames), len(its))) for k in ("raw", "frame-relative", "vs my others", "photo + name")}
    with torch.no_grad():
        for f, (_, path) in enumerate(frames):
            im = Image.open(path).convert("RGB")
            fmap = model.image_embedder(pixel_values=proc(images=im, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
            feats = fmap.reshape(1, -1, fmap.shape[-1])
            L = model.class_predictor(image_feats=feats, query_embeds=Q)[0][0].cpu().numpy()     # (patches, items)
            Lt = model.class_predictor(image_feats=feats, query_embeds=Tq)[0][0].cpu().numpy()   # (patches, items)
            best = L.argmax(0)
            for q in range(len(its)):
                b = best[q]
                others = np.delete(L[b], q)
                scores["raw"][f, q] = L[b, q]
                scores["frame-relative"][f, q] = L[b, q] - np.median(L[:, q])
                scores["vs my others"][f, q] = L[b, q] - others.max()
                scores["photo + name"][f, q] = L[b, q] + Lt[b, q]
    z = lambda a: (a - a.mean()) / (a.std() + 1e-9)
    scores["all three"] = z(scores["frame-relative"]) + z(scores["vs my others"]) + z(scores["photo + name"])

    vid = {}  # frames of the same video (scene)
    for f, (owner, _) in enumerate(frames):
        vid.setdefault(owner, []).append(f)
    out = {}
    rng = np.random.default_rng(0)
    for name, S in scores.items():
        pos, look, other = [], [], []
        pos2, look2, other2 = [], [], []
        for f, (owner, _) in enumerate(frames):
            for q in range(len(its)):
                if q == owner:
                    pos.append(S[f, q])
                elif users[owner] != users[q]:
                    (look if cats[owner] == cats[q] else other).append(S[f, q])
        # two frames of the same scene: the pair passes only if BOTH pass, so the pair score is the min
        for owner, fs in vid.items():
            for _ in range(10):
                a, b = rng.choice(fs, 2, replace=False)
                for q in range(len(its)):
                    s2 = min(S[a, q], S[b, q])
                    if q == owner:
                        pos2.append(s2)
                    elif users[owner] != users[q]:
                        (look2 if cats[owner] == cats[q] else other2).append(s2)
        out[name] = {"one frame": {"vs other category": roc(pos, other), "vs look-alikes": roc(pos, look)},
                     "two frames agree": {"vs other category": roc(pos2, other2), "vs look-alikes": roc(pos2, look2)}}
        o, l = out[name]["one frame"], out[name]["two frames agree"]
        print(f"{name:15} one frame: AUC {o['vs other category']['auc']:.3f} / look-alike {o['vs look-alikes']['auc']:.3f}, "
              f"caught at 1% false {o['vs other category']['tpr_at_1pct_fp']:5.1f}% / {o['vs look-alikes']['tpr_at_1pct_fp']:5.1f}% | "
              f"two frames: caught at 1% false {l['vs other category']['tpr_at_1pct_fp']:5.1f}% / {l['vs look-alikes']['tpr_at_1pct_fp']:5.1f}%", flush=True)
    rep = ROOT / "reports" / "poc25_presence_gate.json"
    allr = json.loads(rep.read_text())
    allr["presence_fixes"] = out
    rep.write_text(json.dumps(allr, indent=2))


if __name__ == "__main__":
    main()
