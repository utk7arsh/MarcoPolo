"""Extra analyses on ARKitScenes upsampling samples (untrusted data; read-only parsing).

1) per-frame bias spread (registration / sync component vs per-pixel noise)
2) error on "protruding small structures": GT pixels that are closer than the local
   (lowres 15x15) median GT by > 15 cm, split by connected-component size in lowres px
3) error after removing per-frame median offset (noise floor estimate)

Usage: python -I arkitscenes_depth_extras.py <video_dir> [<video_dir> ...]
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage


def load(p):
    return np.array(Image.open(p))


def stats(label, e, g):
    if e.size < 50:
        print(f"  {label:<40} n={e.size:>7} (too few)")
        return
    print(f"  {label:<40} n={e.size:>7} bias={e.mean()*100:+6.2f}cm sd={e.std()*100:6.2f}cm "
          f"MAE={np.abs(e).mean()*100:6.2f}cm p90|e|={np.percentile(np.abs(e),90)*100:6.2f}cm "
          f"median GT={np.median(g):.2f} m")


def main(dirs):
    frame_bias = []
    E_res, G_res = [], []
    prot = {"tiny(<=4px)": ([], [], []), "small(5-30px)": ([], [], []), "medium(31-300px)": ([], [], []), "large(>300px)": ([], [], [])}
    for d in dirs:
        for name in sorted(os.listdir(os.path.join(d, "lowres_depth"))):
            low = load(os.path.join(d, "lowres_depth", name)).astype(np.float64) / 1000
            conf = load(os.path.join(d, "confidence", name))
            hi = load(os.path.join(d, "highres_depth", name)).astype(np.float64) / 1000
            H, W = low.shape
            # area-average GT down to lowres grid (7.5x7.5 block), ignoring zeros
            bh, bw = hi.shape[0] // H, hi.shape[1] // W  # 7 x 7 (1440/192=7.5 -> use nearest-center instead)
            vv, uu = np.mgrid[0:H, 0:W]
            hy = np.clip(np.round((vv + 0.5) * hi.shape[0] / H - 0.5).astype(int), 0, hi.shape[0] - 1)
            hx = np.clip(np.round((uu + 0.5) * hi.shape[1] / W - 0.5).astype(int), 0, hi.shape[1] - 1)
            gt = hi[hy, hx]
            valid = (gt > 0) & (low > 0)
            e = low - gt
            fb = np.median(e[valid])
            frame_bias.append(fb)
            E_res.append((e - fb)[valid & (conf == 2)])
            G_res.append(gt[valid & (conf == 2)])
            gfill = np.where(gt > 0, gt, np.nan)
            med = ndimage.generic_filter(np.nan_to_num(gfill, nan=np.nanmedian(gfill)), np.median, size=15, mode="nearest")
            protr = valid & ((med - gt) > 0.15)
            lab, n = ndimage.label(protr)
            if n:
                sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
                for k in range(1, n + 1):
                    s = sizes[k - 1]
                    key = "tiny(<=4px)" if s <= 4 else "small(5-30px)" if s <= 30 else "medium(31-300px)" if s <= 300 else "large(>300px)"
                    m = lab == k
                    prot[key][0].append(e[m])
                    prot[key][1].append(gt[m])
                    # how much of the protrusion does ARKit "see": fraction where lowres is closer than local median by >7.5 cm
                    prot[key][2].append(((med - low)[m] > 0.075).astype(float))
    fb = np.array(frame_bias)
    print(f"frames={fb.size} per-frame median error: mean={fb.mean()*100:+.2f}cm sd={fb.std()*100:.2f}cm "
          f"min={fb.min()*100:+.2f}cm max={fb.max()*100:+.2f}cm")
    print("High-confidence error after removing per-frame median offset (pixel noise floor):")
    e = np.concatenate(E_res)
    g = np.concatenate(G_res)
    bins = [0, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5]
    for lo, hi_ in zip(bins[:-1], bins[1:]):
        m = (g >= lo) & (g < hi_)
        stats(f"{lo:.1f}-{hi_:.1f} m conf=2 (offset-removed)", e[m], g[m])
    print("Protruding structures (GT >15 cm in front of local 15x15 lowres median), by component size in lowres px:")
    for key, (es, gs, seen) in prot.items():
        if not es:
            print(f"  {key:<40} none")
            continue
        ee = np.concatenate(es)
        gg = np.concatenate(gs)
        ss = np.concatenate(seen)
        stats(key, ee, gg)
        print(f"  {'':<40} components={len(es)} fraction of protrusion pixels ARKit also shows >7.5cm in front: {ss.mean()*100:.1f}%")


if __name__ == "__main__":
    main(sys.argv[1:])
