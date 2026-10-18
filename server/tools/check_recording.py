"""Check a recorded session against docs/INTERFACES.md before trusting it (run it on Utkarsh's first recording).

  python tools/check_recording.py data/sessions/<id>

Checks: required meta fields; files present; the JPEG is the unrotated sensor image at image_resolution x jpeg_scale
with no EXIF orientation tag; depth and confidence decode at 256x192; poses are rigid and column-major; intrinsics
look like 1920x1440; timestamps increase; frame, pose and hand rates; hand messages have 21 joints and decodable
patches; the world looks gravity-aligned (the vest phone is portrait, so the image's up is sideways).
Exits non-zero if anything is wrong.
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco import codec, geometry as G  # noqa: E402
from marco.session import Session  # noqa: E402

REQUIRED = ("session_id", "map_id", "frame_id", "t_device", "camera_transform", "intrinsics", "image_resolution")


def check(path):
    problems, notes = [], []
    try:
        ses = Session(path)
    except FileNotFoundError as e:
        return [str(e)], notes
    if not ses.frames:
        return ["no frames"], notes
    last_t, last_id = -1e18, -1
    turns = []
    for m in ses.frames:
        fid = m.get("frame_id")
        missing = [k for k in REQUIRED if k not in m]
        if missing:
            problems.append(f"frame {fid}: missing {missing}")
            continue
        if m["t_device"] <= last_t:
            problems.append(f"frame {fid}: t_device does not increase")
        if fid <= last_id:
            problems.append(f"frame {fid}: frame_id does not increase")
        last_t, last_id = m["t_device"], fid
        try:
            T = G.mat4(m["camera_transform"])
            G.check_pose(T)
            turns.append(G.upright_turns(T))
        except ValueError as e:
            problems.append(f"frame {fid}: {e}")
        K = G.mat3(m["intrinsics"])
        W, H = m["image_resolution"]
        if not (0.6 * W < K[0, 0] < 1.2 * W and abs(K[0, 2] - W / 2) < 0.1 * W and abs(K[1, 2] - H / 2) < 0.1 * H):
            problems.append(f"frame {fid}: intrinsics {K[0, 0]:.0f}/{K[0, 2]:.0f}/{K[1, 2]:.0f} don't fit {W}x{H} (column-major?)")
        try:
            jpeg, d, c = ses.frame_bytes(m)
        except FileNotFoundError as e:
            problems.append(f"frame {fid}: {e}")
            continue
        im = Image.open(io.BytesIO(jpeg))
        s = float(m.get("jpeg_scale", 0.5))
        if abs(im.width - W * s) > 2 or abs(im.height - H * s) > 2:
            problems.append(f"frame {fid}: JPEG {im.width}x{im.height}, expected {W * s:.0f}x{H * s:.0f} (rotated before sending?)")
        if im.getexif().get(0x0112, 1) != 1:
            problems.append(f"frame {fid}: JPEG has an EXIF orientation tag")
        try:
            dep = codec.decode_depth(d)
            codec.decode_conf(c)
            med = float(np.nanmedian(dep))
            if not 0.2 < med < 8:
                problems.append(f"frame {fid}: median depth {med:.2f} m looks wrong (units? metres expected)")
        except ValueError as e:
            problems.append(f"frame {fid}: {e}")
    span = ses.frames[-1]["t_device"] - ses.frames[0]["t_device"]
    if len(ses.frames) > 2 and span > 0:
        fps = (len(ses.frames) - 1) / span
        notes.append(f"frames: {len(ses.frames)} over {span:.0f} s ({fps:.2f}/s)")
        if not 0.5 <= fps <= 2.5:
            problems.append(f"frame rate {fps:.2f}/s; the contract is about 1/s")
    if turns:
        notes.append(f"upright turns (gravity): {max(set(turns), key=turns.count)} (vest portrait mount = 1)")
    poses = [m for m in ses.phone if m.get("type") == "pose"]
    hands = [m for m in ses.phone if m.get("type") == "hand"]
    if poses:
        ts = [m["t_device"] for m in poses]
        if len(ts) > 2 and ts[-1] > ts[0]:
            rate = (len(ts) - 1) / (ts[-1] - ts[0])
            notes.append(f"poses: {len(poses)} ({rate:.1f}/s)")
            if not 5 <= rate <= 30:
                problems.append(f"pose rate {rate:.1f}/s; the contract is about 10/s")
        for m in poses[:50]:
            try:
                G.check_pose(G.mat4(m["camera_transform"]))
            except (ValueError, KeyError) as e:
                problems.append(f"pose at {m.get('t_device')}: {e}")
                break
    else:
        problems.append("no pose messages")
    for m in hands[:200]:
        try:
            if len(m["joints"]) != codec.N_JOINTS:
                raise ValueError(f"{len(m['joints'])} joints, expected {codec.N_JOINTS}")
            codec.decode_patches(m["depth_patches_f16_b64"], "f16", size=int(m.get("patch", 9)))
            codec.decode_patches(m["conf_patches_u8_b64"], "u8", size=int(m.get("patch", 9)))
        except (ValueError, KeyError) as e:
            problems.append(f"hand at {m.get('t_device')}: {e}")
            break
    notes.append(f"hand messages: {len(hands)}")
    return problems, notes


if __name__ == "__main__":
    probs, notes = check(sys.argv[1])
    for n in notes:
        print("  ", n)
    for p in probs[:50]:
        print("PROBLEM:", p)
    print("OK" if not probs else f"{len(probs)} problem(s)")
    sys.exit(1 if probs else 0)
