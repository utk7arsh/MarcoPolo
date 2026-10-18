"""Finding registered items in a frame.

OwlDetector   the real one (POC 22/25/26): OWLv2 image-guided search with the item's one registration photo, plus
              the presence check (photo + name logit, DINOv2 crop check, "looks more like this item than my other
              items"). Thresholds default to POC 26's calibration on ORBIT; refit them on your own props.
              Models: MARCO_OWL_MODEL and MARCO_DINO_MODEL (Hugging Face ids); thresholds belong to a model pair.
TruthDetector for synthetic sessions with ground truth: projects the true item positions into the frame (with
              misses and jitter), so the world model and the dashboard can be tested without any model.

Both return detections in the pixels of the UPRIGHT image they were given.
"""
import logging
import os

import numpy as np

from .. import geometry as G

# TH_DINO was 0.38 (POC 26, ORBIT's handheld photos). From the vest it rejected 13 of 19 correct boxes on the venue
# clips; 0.30 finds 8 of them instead of 5 there with no extra false alarm (POC 28, poc/pocs/poc28_multi_item).
TH = {"photo_name": float(os.environ.get("TH_PHOTO_NAME", "-2.426")), "dino": float(os.environ.get("TH_DINO", "0.30")),
      "vs_others": float(os.environ.get("TH_VS_OTHERS", "0.078"))}
GATE_NAME_SCORE = float(os.environ.get("GATE_NAME_SCORE", "0.05"))
# MARCO_DINO_TURNS=4: compare the DINOv2 crop against the registration crop turned 0/90/180/270 degrees and keep the
# best match (an item lying flat can sit in any direction). On the venue clips it finds more (7 of 18 vs 5 at 0.38) but
# also matches look-alikes more (3 false alarms vs 1 at 0.30), so it's off by default: try it live.
DINO_TURNS = int(os.environ.get("MARCO_DINO_TURNS", "1"))


def _same_name(a, b):
    return " ".join(str(a).lower().split()) == " ".join(str(b).lower().split())


def vs_others(scores, q, names):
    """How far item q's photo logit at its best box beats the best OTHER item's logit at that box ("looks more like
    this item than my other items"). An item registered twice under one name is not an "other": the twins score the
    same everywhere and would veto each other forever. None when no other item is left to compare with."""
    others = [j for j in range(len(names)) if j != q and not _same_name(names[j], names[q])]
    return float(scores[q] - np.max(np.asarray(scores)[others])) if others else None


# Colour check, OFF by default: a detection must not look grossly different from the registration crop (lightness and
# colourfulness). On the venue clips it changed nothing (POC 28). On held-out ORBIT footage it costs 1 in 20 real
# finds (80% -> 75%) for 13.9% -> 12.3% false alarms, about what raising TH_DINO to 0.314 does. It is also the check
# most exposed to lighting (night against day) and to clear items (POC 29). TH_LIGHT=40 TH_CHROMA=30 turns it on.
TH_LIGHT = float(os.environ.get("TH_LIGHT", "inf"))      # CIELAB L*, 0 black ... 100 white
TH_CHROMA = float(os.environ.get("TH_CHROMA", "inf"))    # CIELAB chroma: 0 grey ... ~100 vivid
# Off by default, both measured worse: elongation (seen from the chest a standing bottle looks squat, so the real
# bottle failed it) and trying the top 3 boxes per item (3 false alarms on the clips instead of 1).
TH_SHAPE = float(os.environ.get("TH_SHAPE", "inf"))      # elongation ratio (long side / short side), either way
TOP_K = int(os.environ.get("MARCO_TOP_K", "1"))          # boxes tried per item, best photo score first


def _srgb_to_lab(rgb):
    a = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = a @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def appearance(im):
    """Lightness and colourfulness (median CIELAB L* and chroma) of a crop's middle 60 %, and its elongation."""
    w, h = im.size
    x0, y0 = int(w * 0.2), int(h * 0.2)
    mid = im.crop((x0, y0, max(int(w * 0.8), x0 + 1), max(int(h * 0.8), y0 + 1))).convert("RGB").resize((24, 24))
    lab = _srgb_to_lab(np.asarray(mid, float) / 255)
    return dict(L=float(np.median(lab[..., 0])), C=float(np.median(np.hypot(lab[..., 1], lab[..., 2]))),
                elong=max(w, h) / max(min(w, h), 1))


def appearance_check(ref, cand):
    """'' when the candidate could be the registered item; otherwise what's grossly different about it."""
    if not ref:
        return ""
    bad = []
    if abs(cand["L"] - ref["L"]) > TH_LIGHT:
        bad.append(f"lightness {cand['L']:.0f} vs {ref['L']:.0f}")
    if abs(cand["C"] - ref["C"]) > TH_CHROMA:
        bad.append(f"colourfulness {cand['C']:.0f} vs {ref['C']:.0f}")
    if TH_SHAPE != float("inf") and max(cand["elong"] / ref["elong"], ref["elong"] / cand["elong"]) > TH_SHAPE:
        bad.append(f"shape {cand['elong']:.1f}:1 vs {ref['elong']:.1f}:1")
    return ", ".join(bad)


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def registration_crop(im, box):
    """The exact pixels used as a setup template (also persisted for reload); synthetic detectors have no box."""
    return im.crop(tuple(int(v) for v in box)) if box is not None else im


def _device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class OwlDetector:
    OWL = os.environ.get("MARCO_OWL_MODEL", "google/owlv2-base-patch16-ensemble")
    DINO = os.environ.get("MARCO_DINO_MODEL", "facebook/dinov2-small")

    def __init__(self, owl=None, dino=None):
        import torch
        from transformers import AutoImageProcessor, AutoModel, Owlv2ForObjectDetection, Owlv2Processor
        self.OWL, self.DINO = owl or self.OWL, dino or self.DINO
        self.torch = torch
        self.dev = _device()
        dtype = torch.float16 if self.dev in ("cuda", "mps") else torch.float32
        self.proc = Owlv2Processor.from_pretrained(self.OWL)
        self.owl = Owlv2ForObjectDetection.from_pretrained(self.OWL, use_safetensors=True, dtype=dtype).to(self.dev).eval()
        self.dproc = AutoImageProcessor.from_pretrained(self.DINO)
        self.dino = AutoModel.from_pretrained(self.DINO, use_safetensors=True).to(self.dev).eval()
        self.dtype = dtype
        self.items = {}            # item_id -> dict(name, q_img, q_txt, dino)
        self.fast_pixels = self._check_fast_pixels()
        if not self.fast_pixels:
            logging.getLogger("marco").warning("OWLv2 fast preprocessing disagrees with the processor; using the processor")

    def _check_fast_pixels(self):
        """The GPU path must give the processor's pixels exactly. Checked once at start, landscape and portrait, so a
        different transformers version that pads or resizes differently falls back instead of shifting detections."""
        try:
            ip = self.proc.image_processor
            self.side = int(ip.size["height"])
            self.px_mean = self.torch.tensor(ip.image_mean, device=self.dev).view(1, 3, 1, 1)
            self.px_std = self.torch.tensor(ip.image_std, device=self.dev).view(1, 3, 1, 1)
            from PIL import Image
            rng = np.random.default_rng(0)
            for h, w in ((self.side * 3 // 4, self.side), (self.side, self.side * 3 // 4)):
                im = Image.fromarray(rng.integers(0, 256, (h, w, 3), np.uint8))
                a = self.proc(images=im, return_tensors="pt")["pixel_values"].float()
                b = self._gpu_pixels(im).float().cpu()
                if a.shape != b.shape or float((a - b).abs().max()) > 1e-4:
                    return False
            return True
        except Exception:
            return False

    def _gpu_pixels(self, im):
        """A frame whose long side is already OWLv2's (960 px: the phone's half-size JPEG) only needs zero padding to a
        square and normalising, which the GPU does in a few ms instead of the processor's 20-100 ms on the CPU."""
        w, h = im.size
        x = self.torch.from_numpy(np.array(im)).to(self.dev).permute(2, 0, 1).float().div_(255)
        px = self.torch.zeros((1, 3, self.side, self.side), device=self.dev)
        px[0, :, :h, :w] = x
        return (px - self.px_mean) / self.px_std

    def _pixels(self, im):
        if self.fast_pixels and max(im.size) == self.side and im.mode == "RGB":
            return self._gpu_pixels(im).to(self.dtype)
        return self.proc(images=im, return_tensors="pt")["pixel_values"].to(self.dev, self.dtype)

    def _pass(self, im):
        fmap = self.owl.image_embedder(pixel_values=self._pixels(im))[0]
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
            crop = registration_crop(im, box) if gate else im
            cf, cfe = self._pass(crop)
            q_img = self.owl.embed_image_query(cfe, cf)[0]
            turns = [crop] + [crop.rotate(90 * i, expand=True) for i in range(1, max(DINO_TURNS, 1))]
            self.items[item_id] = dict(name=name, q_img=q_img, q_txt=q_txt, dino=self._dino(turns), look=appearance(crop))
        return dict(quality="ok", reason="", box=box)

    def forget(self, item_id):
        self.items.pop(item_id, None)

    def detect(self, im, **_):
        """For each registered item, its best box in the frame and whether it's there. Up to TOP_K distinct boxes are
        tried per item, best photo score first, and the first that passes every check wins: the best-scoring box is
        often a look-alike (another bottle) while the item itself is the second or third."""
        if not self.items:
            return []
        ids = list(self.items)
        names = [self.items[i]["name"] for i in ids]
        with self.torch.no_grad():
            Q = self.torch.cat([self.items[i]["q_img"] for i in ids], dim=1)
            Tq = self.torch.cat([self.items[i]["q_txt"] for i in ids], dim=1)
            fmap, feats = self._pass(im)
            L = self.owl.class_predictor(image_feats=feats, query_embeds=Q)[0][0].float().cpu().numpy()
            Lt = self.owl.class_predictor(image_feats=feats, query_embeds=Tq)[0][0].float().cpu().numpy()
            boxes = self.owl.box_predictor(feats, fmap)[0].float().cpu().numpy()
            cands, crops = [], []                          # per item: [(patch, box px, index into crops)]
            for q in range(len(ids)):
                picked = []
                for b in np.argsort(-L[:, q])[:60]:
                    box = self._to_px(boxes[b].tolist(), im)
                    if all(_iou(box, pb) <= 0.5 for _, pb, _ in picked):
                        picked.append((int(b), box, len(crops)))
                        crops.append(im.crop(tuple(int(v) for v in box)))
                        if len(picked) >= max(TOP_K, 1):
                            break
                cands.append(picked)
            E = self._dino(crops)
            refs = [self.items[i]["dino"] for i in ids]          # (turns, D), or (D,) for one turn
            sims = self.torch.stack([(refs[q].reshape(-1, E.shape[-1]) @ E[ci]).max()
                                     for q, picked in enumerate(cands) for _, _, ci in picked])
            sims = sims.cpu().tolist()                     # every crop check in one trip back from the GPU
        out, k = [], 0
        for q, iid in enumerate(ids):
            tried = []
            for rank, (b, box, ci) in enumerate(cands[q]):
                d = dict(item_id=iid, name=names[q], box=[round(v, 1) for v in box], photo_name=float(L[b, q] + Lt[b, q]),
                         vs_others=vs_others(L[b], q, names), dino=float(sims[k]), rank=rank,
                         look=appearance_check(self.items[iid].get("look"), appearance(crops[ci])))
                k += 1
                d["present"] = bool(d["photo_name"] >= TH["photo_name"] and d["dino"] >= TH["dino"] and not d["look"]
                                    and (d["vs_others"] is None or d["vs_others"] >= TH["vs_others"]))
                d["score"] = round(1 / (1 + np.exp(-(d["photo_name"] - TH["photo_name"]))), 3)
                tried.append(d)
            ok = [d for d in tried if d["present"]]
            out.append(max(ok, key=lambda d: d["dino"]) if ok else tried[0])
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
