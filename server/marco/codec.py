"""Wire formats from INTERFACES.md: zlib'd float16 depth, zlib'd uint8 confidence, base64 joint patches."""
import base64
import zlib

import numpy as np

DEPTH_W, DEPTH_H = 256, 192
N_JOINTS, PATCH = 21, 9


def inflate(raw: bytes) -> bytes:
    """zlib (RFC 1950) or raw DEFLATE (RFC 1951). Apple's NSData.compressed(using: .zlib) writes raw DEFLATE."""
    try:
        return zlib.decompress(raw)
    except zlib.error:
        try:
            return zlib.decompress(raw, -15)
        except zlib.error as e:
            raise ValueError(f"expected zlib or raw DEFLATE data: {e}") from None


def decode_depth(raw: bytes, w=DEPTH_W, h=DEPTH_H):
    a = np.frombuffer(inflate(raw), dtype="<f2")
    if a.size != w * h:
        raise ValueError(f"depth must be {w}x{h} float16 ({w * h * 2} bytes after zlib), got {a.size * 2} bytes")
    return a.reshape(h, w).astype(np.float32)


def decode_conf(raw: bytes, w=DEPTH_W, h=DEPTH_H):
    a = np.frombuffer(inflate(raw), dtype=np.uint8)
    if a.size != w * h:
        raise ValueError(f"confidence must be {w}x{h} uint8 ({w * h} bytes after zlib), got {a.size} bytes")
    if a.max(initial=0) > 2:
        raise ValueError("confidence values must be 0, 1 or 2 (ARConfidenceLevel)")
    return a.reshape(h, w)


def encode_depth(depth):
    return zlib.compress(np.asarray(depth, dtype="<f2").tobytes(), 6)


def encode_conf(conf):
    return zlib.compress(np.asarray(conf, dtype=np.uint8).tobytes(), 6)


def decode_patches(b64: str, dtype: str, n=N_JOINTS, size=PATCH):
    dt = {"f16": "<f2", "u8": np.uint8}[dtype]
    a = np.frombuffer(base64.b64decode(b64), dtype=dt)
    if a.size != n * size * size:
        raise ValueError(f"expected {n} patches of {size}x{size} ({n * size * size} values), got {a.size}")
    return a.reshape(n, size, size).astype(np.float32 if dtype == "f16" else np.uint8)


def encode_patches(arr, dtype: str):
    dt = {"f16": "<f2", "u8": np.uint8}[dtype]
    return base64.b64encode(np.asarray(arr, dtype=dt).tobytes()).decode()


def patches_from_depth(depth, conf, joints_xy, size=PATCH):
    """What the phone does: a size x size window around each joint's depth pixel (Vision .up coordinates,
    origin bottom-left), padded with NaN / 0 outside the map. Used by the fake session and the tests."""
    h, w = depth.shape
    r = size // 2
    dp = np.full((len(joints_xy), size, size), np.nan, np.float32)
    cp = np.zeros((len(joints_xy), size, size), np.uint8)
    for j, (x, y) in enumerate(joints_xy):
        u, v = int(np.floor(x * w)), int(np.floor((1 - y) * h))
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                uu, vv = u + dx, v + dy
                if 0 <= uu < w and 0 <= vv < h:
                    dp[j, dy + r, dx + r] = depth[vv, uu]
                    cp[j, dy + r, dx + r] = conf[vv, uu]
    return dp, cp
