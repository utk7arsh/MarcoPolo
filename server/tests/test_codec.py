import zlib

import numpy as np
import pytest

from marco import codec


def test_depth_and_confidence_round_trip():
    rng = np.random.default_rng(0)
    d = rng.uniform(0.2, 5.0, (192, 256)).astype(np.float32)
    c = rng.integers(0, 3, (192, 256)).astype(np.uint8)
    assert np.allclose(codec.decode_depth(codec.encode_depth(d)), d, atol=5e-3)    # float16 precision
    assert (codec.decode_conf(codec.encode_conf(c)) == c).all()


def test_raw_deflate_from_apple_is_accepted():
    d = np.full((192, 256), 1.5, np.float32)
    raw = np.asarray(d, "<f2").tobytes()
    co = zlib.compressobj(6, zlib.DEFLATED, -15)            # what NSData.compressed(using: .zlib) produces
    deflated = co.compress(raw) + co.flush()
    assert np.allclose(codec.decode_depth(deflated), 1.5)


def test_wrong_sizes_and_values_are_rejected_with_a_reason():
    with pytest.raises(ValueError, match="256x192"):
        codec.decode_depth(zlib.compress(np.zeros(100, "<f2").tobytes()))
    with pytest.raises(ValueError, match="0, 1 or 2"):
        codec.decode_conf(zlib.compress(np.full(256 * 192, 7, np.uint8).tobytes()))


def test_patches_round_trip_and_padding():
    depth = np.arange(192 * 256, dtype=np.float32).reshape(192, 256) / 1000
    conf = np.full((192, 256), 2, np.uint8)
    joints = [(0.5, 0.5)] * 20 + [(0.0, 1.0)]                # last joint at the image's top-left corner
    dp, cp = codec.patches_from_depth(depth, conf, joints)
    assert dp.shape == (21, 9, 9)
    assert dp[0, 4, 4] == pytest.approx(depth[96, 128])     # centre = the joint's depth pixel (origin bottom-left)
    assert np.isnan(dp[20, 0, 0]) and cp[20, 0, 0] == 0     # outside the map: NaN and confidence 0
    back = codec.decode_patches(codec.encode_patches(dp, "f16"), "f16")
    assert np.allclose(back[0], dp[0], atol=1e-2)
