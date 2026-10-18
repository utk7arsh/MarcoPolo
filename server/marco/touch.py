"""Touch detection from the phone's hand stream (POC 24): 3D, and only while Vision can see the fingertip.

Each hand message carries Vision's 21 joints (orientation .up, so sensor-frame coordinates) and a 9x9 window of
LiDAR depth around each joint.
  fingertip  the near cluster of its window (the finger is the closest surface there), unprojected with the
             latest frame's intrinsics
  contact    the live depth just beyond the fingertip, along the finger, continues the fingertip's depth
             (within CONTACT_M): touching, not hovering in front of or above a surface
  which item the nearest stored item within NEAR_ITEM_M (positions from 1 fps detection are a few cm off, so
             they decide identity, not contact)
Contact is a vote over the last VOTE_N messages (single LiDAR pixels are noisy). A touch starts once the vote
reaches VOTE_ON on the same nearby item for STREAK messages with the knuckles nearly still; it ends when the vote
falls to VOTE_OFF or the fingertip is LEAVE_M from the item. Thresholds are simulation-tuned: refit on device. A hidden fingertip (low
Vision confidence) never counts: its depth would be whatever is in front of it.
"""
import uuid

import numpy as np

from . import codec, geometry as G

CONTACT_M = 0.025         # depth past the fingertip within this of the fingertip's depth: touching a surface
NEAR_ITEM_M = 0.15         # identity: the nearest stored item within this (stored positions are a few cm off)
LEAVE_M = 0.20
VOTE_N, VOTE_ON, VOTE_OFF = 5, 0.6, 0.2   # contact = share of the last VOTE_N messages with contact
STREAK = 2                 # at 15 Hz: about 130 ms
MIN_TIP_CONF = 0.5
STILL_PX = 16.0            # knuckle motion per message (1920x1440 px) at 15 Hz
JOINTS = ["wrist", "thumbCMC", "thumbMP", "thumbIP", "thumbTip", "indexMCP", "indexPIP", "indexDIP", "indexTip",
          "middleMCP", "middlePIP", "middleDIP", "middleTip", "ringMCP", "ringPIP", "ringDIP", "ringTip",
          "littleMCP", "littlePIP", "littleDIP", "littleTip"]


def dist_to_item(p, center, size_m):
    """Distance from point p to an item modelled as a vertical cylinder standing on its footprint `center`."""
    r = max(size_m / 2, 0.02)
    h = max(size_m, 0.02)
    dr = max(0.0, float(np.hypot(p[0] - center[0], p[2] - center[2])) - r)
    dy = max(0.0, center[1] - p[1], p[1] - (center[1] + h))
    return float(np.hypot(dr, dy))


class TouchDetector:
    def __init__(self):
        self.K = None
        self.res = None
        self.current = None        # item_id being touched
        self.touch_id = None
        self.streak = (None, 0)
        self.knuckles = []         # recent indexMCP pixels
        self.tip = None            # latest visible fingertip (world)
        self.tip_t = None
        self.votes = []            # recent contact flags

    def set_camera(self, K, res):
        self.K, self.res = K, res

    def fingertip(self, msg):
        """(world position of the index fingertip, contact?) or (None, False) if hidden or without depth."""
        if self.K is None:
            return None, False
        joints = {j["name"]: j for j in msg["joints"]}
        tip, dip = joints.get("indexTip"), joints.get("indexDIP")
        if tip is None or tip.get("conf", 0) < MIN_TIP_CONF:
            return None, False
        size = int(msg.get("patch", codec.PATCH))
        dp = codec.decode_patches(msg["depth_patches_f16_b64"], "f16", size=size)
        cp = codec.decode_patches(msg["conf_patches_u8_b64"], "u8", size=size)
        k = [j["name"] for j in msg["joints"]].index("indexTip")
        c = size // 2
        win, cw = dp[k, c - 2:c + 3, c - 2:c + 3], cp[k, c - 2:c + 3, c - 2:c + 3]
        good = win[(cw >= 1) & np.isfinite(win)]
        if good.size < 3:
            return None, False
        q = float(np.percentile(good, 25))              # the finger is the nearest surface around its tip:
        z_tip = float(np.median(good[good <= q + 0.03]))  # the median of that near cluster (unbiased by noise)
        W, H = self.res
        T = G.mat4(msg["camera_transform"])
        fr = G.Frame(T, self.K, (W, H), np.zeros((1, 1), np.float32), np.zeros((1, 1), np.uint8))
        p = fr.unproject(tip["x"] * W, (1 - tip["y"]) * H, z_tip)
        contact = False
        if dip is not None:
            d = np.array([(tip["x"] - dip["x"]) * codec.DEPTH_W, -(tip["y"] - dip["y"]) * codec.DEPTH_H])
            n = np.linalg.norm(d)
            if n > 1e-6:
                d /= n
                beyond = []
                for s in (2, 3, 4):                      # depth pixels past the tip, along the finger
                    for side in (-1, 0, 1):
                        x = int(round(c + d[0] * s - d[1] * side))
                        y = int(round(c + d[1] * s + d[0] * side))
                        if 0 <= x < size and 0 <= y < size and cp[k, y, x] >= 1 and np.isfinite(dp[k, y, x]):
                            beyond.append(float(dp[k, y, x]))
                if len(beyond) >= 3:
                    contact = abs(float(np.median(beyond)) - z_tip) <= CONTACT_M
        return p, contact

    def update(self, msg, items, t, target_id=None):
        """items: {item_id: (center, size_m)}. Returns server->phone messages and the touched item (if a touch began)."""
        out, began = [], None
        joints = {j["name"]: j for j in msg["joints"]}
        if self.res is not None and "indexMCP" in joints:
            W, H = self.res
            self.knuckles = (self.knuckles + [(joints["indexMCP"]["x"] * W, (1 - joints["indexMCP"]["y"]) * H)])[-4:]
        p, contact = self.fingertip(msg)
        if p is not None:
            self.tip, self.tip_t = p, t
            self.votes = (self.votes + [contact])[-VOTE_N:]
        else:
            self.votes = (self.votes + [False])[-VOTE_N:]
        share = sum(self.votes) / max(len(self.votes), 1)
        hit = None
        if p is not None and items:
            ds = {iid: dist_to_item(p, c, s) for iid, (c, s) in items.items()}
            k = min(ds, key=ds.get)
            if self.current is not None:                  # keep a touch until contact fades or the hand leaves
                if k == self.current and ds[k] <= LEAVE_M and share > VOTE_OFF:
                    hit = k
            elif share >= VOTE_ON and ds[k] <= NEAR_ITEM_M:
                hit = k
            if target_id in ds:
                out.append(dict(type="hand_proximity", item_id=target_id, distance_m=round(ds[target_id], 3)))
        # Motion needs 3 knuckle samples; until then the hand does not count as still.
        moving = len(self.knuckles) < 3 or float(np.median(np.linalg.norm(np.diff(np.array(self.knuckles), axis=0), axis=1))) > STILL_PX
        if hit is not None and hit != self.current and moving:
            hit = None
        prev, n = self.streak
        self.streak = (hit, n + 1 if hit == prev else 1)
        if hit != self.current:
            if self.current is not None and (hit is None or self.streak[1] >= STREAK):
                out.append(dict(type="touch_end", touch_id=self.touch_id))
                self.current, self.touch_id = None, None
            if hit is not None and self.streak[1] >= STREAK:
                self.current, self.touch_id = hit, uuid.uuid4().hex[:12]
                out.append(dict(type="touch", touch_id=self.touch_id, item_id=hit, position=[round(float(v), 3) for v in p],
                                t_device=t))
                began = hit
        return out, began
