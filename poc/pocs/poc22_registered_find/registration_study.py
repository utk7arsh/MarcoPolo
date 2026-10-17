"""POC 22 add-on: how should the registration be used with OWLv2? (one image pass per test frame, all variants at once)

Per item: the 6 registration crops and the name are encoded once. Per test frame: one OWLv2 image pass, then
the class head scores every patch against every photo and the name, and each variant picks its top box:
  photo k              each single registration photo on its own (how much does the choice of photo matter?)
  first named photo    the first photo in which the name detector found the item (the rule bench.py uses)
  named photos         every photo the name detector boxed, combined (falls back to the first photo)
  any / average / merged over 3 or 6 photos, with or without the name added
Same items, frames, mosaics and IoU >= 0.5 scoring as bench.py.
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


def main():
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(OWL)
    model = Owlv2ForObjectDetection.from_pretrained(OWL, use_safetensors=True).to(B.DEV).eval()
    base = B.items()
    out, per_item, named_flags = {}, {}, {}
    for task, its in (("own_clutter", base), ("lookalikes", B.mosaic_items(base))):
        hits = {}
        for it in its:
            name = B.NAMES.get(it["obj"], it["obj"].replace("-", " "))
            named = [f for f in it["reg_order"] if (it["regdir"] / "boxes_text.json").exists()
                     and f in json.loads((it["regdir"] / "boxes_text.json").read_text())]
            with torch.no_grad():
                q = []
                for rf in it["reg_order"]:
                    crop = Image.open(it["regdir"] / rf).convert("RGB").crop(tuple(int(v) for v in it["reg"][rf]))
                    qmap = model.image_embedder(pixel_values=proc(images=crop, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
                    q.append(model.embed_image_query(qmap.reshape(1, -1, qmap.shape[-1]), qmap)[0])
                Q = torch.cat(q, dim=1)                                     # (1, n_photos, 512), in reg_order
                tok = proc(text=[[f"a photo of {name}"]], return_tensors="pt").to(B.DEV)
                T = model.owlv2.get_text_features(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"]).pooler_output[:, None, :]
            idx = {f: i for i, f in enumerate(it["reg_order"])}
            named_idx = [idx[f] for f in named] or [0]
            named_flags[it["name"]] = [f in named for f in it["reg_order"]]
            for path, gt in it["tests"]:
                im = Image.open(path).convert("RGB")
                with torch.no_grad():
                    fmap = model.image_embedder(pixel_values=proc(images=im, return_tensors="pt")["pixel_values"].to(B.DEV))[0]
                    feats = fmap.reshape(1, -1, fmap.shape[-1])
                    L = model.class_predictor(image_feats=feats, query_embeds=Q)[0][0]          # (patches, n_photos)
                    Lt = model.class_predictor(image_feats=feats, query_embeds=T)[0][0, :, 0]   # (patches,)

                    def merged(sel):
                        p = torch.nn.functional.normalize(Q[:, sel], dim=-1).mean(dim=1, keepdim=True)
                        return model.class_predictor(image_feats=feats, query_embeds=p)[0][0, :, 0]

                    boxes = model.box_predictor(feats, fmap)[0].cpu().numpy()
                    scores = {f"photo {k + 1}": L[:, k] for k in range(L.shape[1])}
                    scores["first named photo"] = L[:, named_idx[0]]
                    scores["first named photo + name"] = L[:, named_idx[0]] + Lt
                    scores["named photos, averaged"] = L[:, named_idx].mean(dim=-1)
                    scores["named photos, merged"] = merged(named_idx)
                    scores["named photos, merged + name"] = merged(named_idx) + Lt
                    for n in (3, 6):
                        scores[f"{n} photos, any"] = L[:, :n].max(dim=-1).values
                        scores[f"{n} photos, averaged"] = L[:, :n].mean(dim=-1)
                        scores[f"{n} photos, merged"] = merged(list(range(min(n, L.shape[1]))))
                        scores[f"{n} photos, averaged + name"] = L[:, :n].mean(dim=-1) + Lt
                    scores["name only"] = Lt
                side = max(im.size)
                for k, s in scores.items():
                    cx, cy, w, h = boxes[int(s.argmax())]
                    b = [(cx - w / 2) * side, (cy - h / 2) * side, (cx + w / 2) * side, (cy + h / 2) * side]
                    hits.setdefault(k, []).append(B.iou(b, gt) >= 0.5)
                    per_item.setdefault(task, {}).setdefault(k, {}).setdefault(it["name"], []).append(bool(B.iou(b, gt) >= 0.5))
        out[task] = {k: round(100 * float(np.mean(v)), 1) for k, v in hits.items()}
        print(f"\n## {task}", flush=True)
        for k, v in out[task].items():
            print(f"  {k:32} {v:5.1f}%")
    singles = [k for k in out["own_clutter"] if k.startswith("photo ")]
    for task in out:
        v = [out[task][k] for k in singles]
        out[task]["single photo: mean of photos 1-6"] = round(float(np.mean(v)), 1)
        out[task]["single photo: worst"] = min(v)
    # one-shot registration: does "the name detector found the item in the photo" predict a good photo?
    for task in out:
        for flag, label in ((True, "single photo the name detector boxed"), (False, "single photo it could not box")):
            h = [x for item, fl in named_flags.items() for k, f in enumerate(fl) if f == flag
                 for x in per_item[task].get(f"photo {k + 1}", {}).get(item, [])]
            out[task][label] = round(100 * float(np.mean(h)), 1) if h else None
            out[task][label + " (n photos)"] = sum(f == flag for fl in named_flags.values() for f in fl)
        print(task, {k: v for k, v in out[task].items() if k.startswith("single photo")})
    out["per_item"] = {t: {k: {i: round(float(np.mean(v)), 2) for i, v in d.items()} for k, d in pv.items()} for t, pv in per_item.items()}
    out["named_flags"] = named_flags
    (ROOT / "reports" / "poc22_registration_study.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
