"""Summarize ARKitScenes .pincam intrinsics directories (untrusted data; read-only parsing).

Usage: python -I pincam_summary.py <dir_with_pincam_files> [<dir2> ...]
Each .pincam is one line: width height fx fy cx cy (no trailing newline).
"""
import math
import os
import sys


def summarize(d):
    rows = []
    for name in sorted(os.listdir(d)):
        if not name.endswith(".pincam"):
            continue
        with open(os.path.join(d, name), "r") as fh:
            parts = fh.read().split()
        if len(parts) != 6:
            continue
        w, h, fx, fy, cx, cy = map(float, parts)
        ts = float(name.rsplit("_", 1)[1][: -len(".pincam")])
        rows.append((ts, w, h, fx, fy, cx, cy))
    if not rows:
        print(d, "no pincam files")
        return
    rows.sort()
    n = len(rows)

    def stats(i):
        vals = [r[i] for r in rows]
        mean = sum(vals) / n
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
        return min(vals), max(vals), mean, sd

    w, h = rows[0][1], rows[0][2]
    dur = rows[-1][0] - rows[0][0]
    print(f"== {d}")
    print(f"frames={n} size={int(w)}x{int(h)} t0={rows[0][0]:.3f} t1={rows[-1][0]:.3f} dur={dur:.2f}s mean_rate={(n - 1) / dur if dur > 0 else float('nan'):.2f} fps")
    for label, i in (("fx", 3), ("fy", 4), ("cx", 5), ("cy", 6)):
        mn, mx, mean, sd = stats(i)
        print(f"  {label}: min={mn:.3f} max={mx:.3f} mean={mean:.3f} sd={sd:.3f}")
    fx_mean = stats(3)[2]
    fy_mean = stats(4)[2]
    hfov = 2 * math.degrees(math.atan(w / (2 * fx_mean)))
    vfov = 2 * math.degrees(math.atan(h / (2 * fy_mean)))
    dfov = 2 * math.degrees(math.atan(math.hypot(w, h) / (2 * fx_mean)))
    print(f"  implied HFOV={hfov:.2f} deg VFOV={vfov:.2f} deg DFOV={dfov:.2f} deg (from mean fx/fy)")
    print(f"  fx==fy in all frames: {all(abs(r[3] - r[4]) < 1e-6 for r in rows)}")
    # gaps between consecutive timestamps
    gaps = [rows[k + 1][0] - rows[k][0] for k in range(n - 1)]
    if gaps:
        gaps_sorted = sorted(gaps)
        print(f"  dt: min={gaps_sorted[0]:.4f} median={gaps_sorted[len(gaps) // 2]:.4f} max={gaps_sorted[-1]:.4f}")
    print("  first 3 rows:", rows[:3])


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        summarize(arg)
