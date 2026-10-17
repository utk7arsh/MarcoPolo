"""Read SOFA (AES69, HDF5-based) HRIR files with h5py.

Converts SOFA spherical coordinates (azimuth counter-clockwise from front, i.e. +90 = LEFT)
to this project's convention: azimuth clockwise from front (+90 = RIGHT), elevation up.
"""
from pathlib import Path

import h5py
import numpy as np

DOWNLOADS = Path(__file__).resolve().parents[2] / "data" / "downloads"


def load_sofa(path):
    with h5py.File(path, "r") as f:
        ir = np.array(f["Data.IR"], dtype=np.float64)  # (M, R=2, N)
        fs = float(np.array(f["Data.SamplingRate"]).ravel()[0])
        pos = np.array(f["SourcePosition"], dtype=np.float64)  # (M, 3) az, el, r (deg, deg, m)
        units = f["SourcePosition"].attrs.get("Units", b"")
    az_ccw = pos[:, 0]
    az = (-az_ccw + 180.0) % 360.0 - 180.0  # clockwise, [-180, 180)
    el = pos[:, 1]
    return dict(ir=ir, az=az, el=el, dist=pos[:, 2], fs=fs, units=units, path=str(path))


def ari_subjects():
    return sorted(DOWNLOADS.glob("ari_dtf_*/dtf_*.sofa"), key=lambda p: int(p.stem.split("nh")[1]))
