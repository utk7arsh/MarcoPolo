"""Summarize an ARKitScenes .traj file (untrusted data; read-only parsing).

Format per line: timestamp rx ry rz tx ty tz  (axis-angle rotation in radians, translation in meters).
Usage: python -I traj_summary.py <file.traj>
"""
import math
import sys

import numpy as np


def rodrigues(rv):
    theta = np.linalg.norm(rv)
    if theta < 1e-12:
        return np.eye(3)
    k = rv / theta
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(theta) * K + (1 - math.cos(theta)) * (K @ K)


def main(path):
    data = np.loadtxt(path)
    ts = data[:, 0]
    rv = data[:, 1:4]
    t = data[:, 4:7]
    n = len(ts)
    dt = np.diff(ts)
    print(f"poses={n} dur={ts[-1] - ts[0]:.2f}s dt median={np.median(dt):.4f} min={dt.min():.4f} max={dt.max():.4f} -> {1 / np.median(dt):.2f} Hz")
    # The .traj stores world->camera or camera->world? Compute both camera centers.
    Rs = [rodrigues(r) for r in rv]
    # Hypothesis A: (R,t) maps world->camera; camera center C = -R^T t
    CA = np.array([-R.T @ tt for R, tt in zip(Rs, t)])
    # Hypothesis B: (R,t) maps camera->world; camera center C = t
    CB = t
    for label, C in (("A: world->cam (C=-R^T t)", CA), ("B: cam->world (C=t)", CB)):
        steps = np.linalg.norm(np.diff(C, axis=0), axis=1)
        speed = steps / dt
        print(f"  {label}: path={steps.sum():.2f} m, bbox extent={np.ptp(C, axis=0).round(2)}, speed median={np.median(speed):.3f} p95={np.percentile(speed, 95):.3f} max={speed.max():.3f} m/s")
    # angular speed between consecutive frames
    ang = []
    for k in range(n - 1):
        Rrel = Rs[k + 1] @ Rs[k].T
        c = (np.trace(Rrel) - 1) / 2
        ang.append(math.degrees(math.acos(max(-1.0, min(1.0, c)))))
    ang = np.array(ang) / dt
    print(f"  angular speed deg/s: median={np.median(ang):.1f} p95={np.percentile(ang, 95):.1f} max={ang.max():.1f}")


if __name__ == "__main__":
    main(sys.argv[1])
