"""Compare ARKit LiDAR lowres_depth (256x192) vs Faro-derived highres_depth GT (1920x1440) in an
ARKitScenes upsampling sample (untrusted data; read-only parsing).

Usage: python -I arkitscenes_depth_error.py <video_dir> [<video_dir> ...] [tro_csv]
"""
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage


def load(path):
    return np.array(Image.open(path))


def main(vdirs, tro_csv=None):
    tro = {}
    if tro_csv:
        with open(tro_csv) as fh:
            for line in fh.read().replace("\r", "").splitlines()[1:]:
                k, v = line.split(",")
                tro[k] = v == "True"
    names = [(vdir, n) for vdir in vdirs for n in sorted(os.listdir(os.path.join(vdir, "lowres_depth")))]
    E, G, C, EDGE, FR = [], [], [], [], []
    conf_hist = np.zeros(3, dtype=np.int64)
    zero_low = 0
    total_low = 0
    for vdir, name in names:
        low = load(os.path.join(vdir, "lowres_depth", name)).astype(np.float64) / 1000.0
        conf = load(os.path.join(vdir, "confidence", name))
        hi = load(os.path.join(vdir, "highres_depth", name)).astype(np.float64) / 1000.0
        H, W = low.shape
        sy, sx = hi.shape[0] / H, hi.shape[1] / W
        vv, uu = np.mgrid[0:H, 0:W]
        hy = np.clip(np.round((vv + 0.5) * sy - 0.5).astype(int), 0, hi.shape[0] - 1)
        hx = np.clip(np.round((uu + 0.5) * sx - 0.5).astype(int), 0, hi.shape[1] - 1)
        gt = hi[hy, hx]
        # GT depth discontinuity mask at lowres scale: max-min of GT within a 3x3 lowres neighbourhood > 10% of depth
        gt_nan = np.where(gt > 0, gt, np.nan)
        gmax = ndimage.maximum_filter(np.nan_to_num(gt_nan, nan=0.0), size=3)
        gmin = -ndimage.maximum_filter(-np.nan_to_num(gt_nan, nan=1e9), size=3)
        edge = (gmax - gmin) > 0.10 * np.maximum(gt, 1e-6)
        valid = (gt > 0) & (low > 0)
        for c in range(3):
            conf_hist[c] += int((conf == c).sum())
        zero_low += int((low == 0).sum())
        total_low += low.size
        E.append((low - gt)[valid])
        G.append(gt[valid])
        C.append(conf[valid])
        EDGE.append(edge[valid])
        FR.append(np.full(valid.sum(), tro.get(name[:-4], False)))
    e = np.concatenate(E)
    g = np.concatenate(G)
    c = np.concatenate(C)
    ed = np.concatenate(EDGE)
    fr = np.concatenate(FR)
    print(f"frames={len(names)} valid_pairs={e.size} lowres_zero_frac={zero_low / total_low:.4f}")
    print(f"confidence pixel share (all pixels): low={conf_hist[0] / conf_hist.sum():.3f} med={conf_hist[1] / conf_hist.sum():.3f} high={conf_hist[2] / conf_hist.sum():.3f}")
    print(f"GT depth range of valid pairs: {g.min():.2f}..{g.max():.2f} m, median {np.median(g):.2f} m")

    def row(label, m):
        if m.sum() < 50:
            print(f"  {label:<28} n={int(m.sum()):>7}  (too few)")
            return
        ee = e[m]
        gg = g[m]
        print(f"  {label:<28} n={int(m.sum()):>7} bias={ee.mean() * 100:+6.2f}cm sd={ee.std() * 100:6.2f}cm "
              f"MAE={np.abs(ee).mean() * 100:6.2f}cm RMSE={np.sqrt((ee ** 2).mean()) * 100:6.2f}cm "
              f"AbsRel={np.mean(np.abs(ee) / gg) * 100:5.2f}% p90|e|={np.percentile(np.abs(ee), 90) * 100:6.2f}cm "
              f"d<1.05={np.mean(np.maximum(gg / (gg + ee), (gg + ee) / gg) < 1.05) * 100:5.1f}% "
              f"conf(L/M/H)={np.mean(c[m] == 0) * 100:4.1f}/{np.mean(c[m] == 1) * 100:4.1f}/{np.mean(c[m] == 2) * 100:4.1f}%")

    print("By GT distance (all confidences):")
    bins = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0]
    for lo, hi_ in zip(bins[:-1], bins[1:]):
        row(f"{lo:.1f}-{hi_:.1f} m", (g >= lo) & (g < hi_))
    print("By confidence:")
    for k, lab in enumerate(["low(0)", "medium(1)", "high(2)"]):
        row(lab, c == k)
    print("By distance, high confidence only:")
    for lo, hi_ in zip(bins[:-1], bins[1:]):
        row(f"{lo:.1f}-{hi_:.1f} m conf=2", (g >= lo) & (g < hi_) & (c == 2))
    print("Edges vs non-edges (GT discontinuity >10% within 3x3 lowres px):")
    row("edge pixels", ed)
    row("non-edge pixels", ~ed)
    if tro:
        print("Frames annotated transparent/reflective (Has_TRO):")
        row("TRO frames", fr)
        row("non-TRO frames", ~fr)


if __name__ == "__main__":
    dirs = [a for a in sys.argv[1:] if os.path.isdir(a)]
    csvs = [a for a in sys.argv[1:] if a.endswith(".csv")]
    main(dirs, csvs[0] if csvs else None)
