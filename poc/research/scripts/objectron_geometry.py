"""Minimal stdlib protobuf decoder for Objectron geometry.pbdata (sequence of <uint32 LE length><ARFrame>).
Untrusted data; read-only parsing. Field numbers from objectron/schema/a_r_capture_metadata.proto.

Usage: python -I objectron_geometry.py <geometry.pbdata>
"""
import math
import struct
import sys
from collections import Counter


def varint(buf, i):
    shift = 0
    out = 0
    while True:
        b = buf[i]
        i += 1
        out |= (b & 0x7F) << shift
        if not b & 0x80:
            return out, i
        shift += 7


def fields(buf):
    """Yield (field_number, wire_type, value) for a message buffer."""
    i = 0
    n = len(buf)
    while i < n:
        key, i = varint(buf, i)
        fn, wt = key >> 3, key & 7
        if wt == 0:
            v, i = varint(buf, i)
        elif wt == 1:
            v = buf[i:i + 8]
            i += 8
        elif wt == 2:
            ln, i = varint(buf, i)
            v = buf[i:i + ln]
            i += ln
        elif wt == 5:
            v = buf[i:i + 4]
            i += 4
        else:
            raise ValueError(f"unsupported wire type {wt}")
        yield fn, wt, v


def packed_floats(b):
    return list(struct.unpack("<%df" % (len(b) // 4), b))


TRACK = {0: "UNDEFINED", 1: "UNAVAILABLE", 2: "LIMITED", 3: "NORMAL"}
REASON = {0: "UNDEFINED", 1: "NONE", 2: "INITIALIZING", 3: "EXCESSIVE_MOTION", 4: "INSUFFICIENT_FEATURES", 5: "RELOCALIZING"}


def parse_camera(b):
    cam = {"intrinsics": [], "transform": [], "proj": [], "view": []}
    for fn, wt, v in fields(b):
        if fn == 1:
            cam["tracking_state"] = TRACK.get(v, v)
        elif fn == 2:
            cam["reason"] = REASON.get(v, v)
        elif fn == 3:
            cam["transform"] += packed_floats(v) if wt == 2 else [struct.unpack("<f", v)[0]]
        elif fn == 5:
            cam["w"] = v
        elif fn == 6:
            cam["h"] = v
        elif fn == 7:
            cam["intrinsics"] += packed_floats(v) if wt == 2 else [struct.unpack("<f", v)[0]]
        elif fn == 8:
            cam["proj"] += packed_floats(v) if wt == 2 else [struct.unpack("<f", v)[0]]
        elif fn == 9:
            cam["view"] += packed_floats(v) if wt == 2 else [struct.unpack("<f", v)[0]]
    return cam


def main(path):
    with open(path, "rb") as fh:
        data = fh.read()
    i = 0
    frames = []
    has_depth = 0
    n_feature_pts = []
    n_planes = []
    while i + 4 <= len(data):
        ln = struct.unpack("<I", data[i:i + 4])[0]
        i += 4
        msg = data[i:i + ln]
        i += ln
        fr = {"planes": 0}
        for fn, wt, v in fields(msg):
            if fn == 1:
                fr["t"] = struct.unpack("<d", v)[0]
            elif fn == 2:
                has_depth += 1
            elif fn == 4:
                fr["cam"] = parse_camera(v)
            elif fn == 7:
                fr["planes"] += 1
            elif fn == 8:
                cnt = 0
                for f2, w2, v2 in fields(v):
                    if f2 == 2:
                        cnt += 1
                n_feature_pts.append(cnt)
        n_planes.append(fr["planes"])
        frames.append(fr)
    print(f"frames={len(frames)} frames_with_depth_data={has_depth}")
    ts = [f["t"] for f in frames if "t" in f]
    if len(ts) > 1:
        dts = sorted(b - a for a, b in zip(ts, ts[1:]))
        print(f"duration={ts[-1] - ts[0]:.2f}s median dt={dts[len(dts) // 2]:.4f}s -> {1 / dts[len(dts) // 2]:.2f} fps")
    cams = [f["cam"] for f in frames if "cam" in f]
    sizes = Counter((c.get("w"), c.get("h")) for c in cams)
    print("image resolution(s):", dict(sizes))
    states = Counter((c.get("tracking_state", "UNAVAILABLE(default)"), c.get("reason", "NONE(default)")) for c in cams)
    print("tracking state/reason counts:", dict(states))
    K = [c["intrinsics"] for c in cams if len(c["intrinsics"]) == 9]
    if K:
        print("first K (as stored, 9 floats):", [round(x, 3) for x in K[0]])
        # Objectron stores K row-major: [fx,0,cx, 0,fy,cy, 0,0,1] (verified: K[6]=K[7]=0)
        fx = [k[0] for k in K]
        fy = [k[4] for k in K]
        cx = [k[2] for k in K]
        cy = [k[5] for k in K]
        for lab, arr in (("fx", fx), ("fy", fy), ("cx", cx), ("cy", cy)):
            m = sum(arr) / len(arr)
            print(f"  {lab}: min={min(arr):.3f} max={max(arr):.3f} mean={m:.3f}")
        w, h = cams[0].get("w"), cams[0].get("h")
        mfx = sum(fx) / len(fx)
        mfy = sum(fy) / len(fy)
        print(f"  implied HFOV={2 * math.degrees(math.atan(w / (2 * mfx))):.2f} deg VFOV={2 * math.degrees(math.atan(h / (2 * mfy))):.2f} deg for {w}x{h}")
    P = [c["proj"] for c in cams if len(c["proj"]) == 16]
    if P:
        print("first projection matrix (16 floats, column-major):", [round(x, 4) for x in P[0]])
    if n_feature_pts:
        s = sorted(n_feature_pts)
        print(f"raw feature points per frame: min={s[0]} median={s[len(s) // 2]} max={s[-1]}")
    print(f"plane anchors per frame: max={max(n_planes)} last={n_planes[-1]}")
    # camera translation path from transform (camera->world 4x4, row-major: translation at 3,7,11)
    T = [c["transform"] for c in cams if len(c["transform"]) == 16]
    if T:
        print("first transform (row-major):", [round(x, 3) for x in T[0]])
    if len(T) > 1:
        pts = [(t[3], t[7], t[11]) for t in T]
        path = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        print(f"camera path length={path:.2f} m over {len(T)} poses")


if __name__ == "__main__":
    main(sys.argv[1])
