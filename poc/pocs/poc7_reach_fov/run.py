"""POC 7: Can the chest camera see the item (and the hand) in the last arm's length?

Real ARKit wide-camera FOV (measured fx=1600 @1920x1440): portrait lanyard -> 48.4 deg horizontal,
61.9 deg vertical. Chest camera at 1.30 m. For several downward mount tilts we check, using the
emulator's own projection: what's the nearest visible point on a table top (0.75 m) / coffee table
(0.45 m) / floor; are items at 0.35-0.6 m from the chest in frame; and how high up a shelf the
camera still sees at 2 m.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "arkit"))
from device import IMG_H, IMG_W, chest_camera_pose, project  # noqa: E402


def in_frame(T, p, margin=60):
    uv, z = project(T, np.asarray(p, float)[None])
    return bool(z[0] > 0.05 and margin <= uv[0, 0] <= IMG_W - margin and margin <= uv[0, 1] <= IMG_H - margin)


def nearest_visible(T, height, cam_xz=(0, 0)):
    """Nearest horizontal distance (from the phone) straight ahead at which a surface point is in frame."""
    phone = T[:3, 3]
    for d in np.arange(0.05, 6, 0.01):
        if in_frame(T, [phone[0], height, phone[2] - d]):
            return round(float(d), 2)
    return None


def highest_visible(T, dist):
    phone = T[:3, 3]
    hs = [h for h in np.arange(0, 2.6, 0.01) if in_frame(T, [phone[0], h, phone[2] - dist])]
    return round(float(max(hs)), 2) if hs else None


if __name__ == "__main__":
    res = {}
    for tilt in (0, 15, 25, 35, 45):
        T = chest_camera_pose((0, 0), 0, 0, tilt_deg=tilt)
        phone = T[:3, 3]
        reach = {f"{d} m": in_frame(T, [phone[0], 0.75, phone[2] - d]) for d in (0.35, 0.45, 0.6)}
        reach_side = {f"{d} m, 20 cm to the side": in_frame(T, [phone[0] + 0.2, 0.75, phone[2] - d]) for d in (0.35, 0.45, 0.6)}
        hand = in_frame(T, [phone[0] + 0.1, 0.95, phone[2] - 0.45])  # hand hovering 20 cm above the item
        res[f"tilt {tilt} deg"] = {
            "nearest visible dining-table point (0.75 m high)": nearest_visible(T, 0.75),
            "nearest visible coffee-table point (0.45 m)": nearest_visible(T, 0.45),
            "nearest visible floor point": nearest_visible(T, 0.0),
            "item on dining table at": reach, "item on table, offset": reach_side,
            "hand above item at 0.45 m visible": hand,
            "highest visible point at 2 m (m)": highest_visible(T, 2.0),
        }
        print(f"\n## mount tilt {tilt} deg down")
        for k, v in res[f"tilt {tilt} deg"].items():
            print(f"  {k}: {v}")
    (ROOT / "reports" / "poc7_reach_fov.json").write_text(json.dumps(res, indent=2))
