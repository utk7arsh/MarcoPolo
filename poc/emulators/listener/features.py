"""Auditory features of an HRIR set on a regular head-frame direction grid.

Features (per direction):
  itd_us  : interaural time difference from onset times (+ = source on the right)
  ild_db  : per-band interaural level difference (L - R, dB), band-limited 0.7-16 kHz
  spec_db : per-ear spectral profile gradient (dB/band), the monaural cue humans use for
            front/back and elevation (cf. Baumgartner et al. 2014 sagittal-plane model)
The grid is regular so a head rotation in yaw is a circular shift in azimuth.
"""
import numpy as np
from scipy.signal import butter, resample, sosfiltfilt

AZ_STEP = 2.5
GRID_AZ = np.arange(-180.0, 180.0, AZ_STEP)                       # 144
GRID_EL = np.array([-45, -30, -20, -10, 0, 10, 20, 30, 45, 60], float)  # 10
N_BANDS = 20
BAND_EDGES = np.geomspace(700.0, 16000.0, N_BANDS + 1)


def _unit(az, el):
    a, e = np.radians(az), np.radians(el)
    return np.stack([np.cos(e) * np.sin(a), np.sin(e), -np.cos(e) * np.cos(a)], -1)


def onset_s(x, fs, up=8, thr=0.15):
    y = np.abs(resample(x, len(x) * up))
    return np.argmax(y >= thr * y.max()) / (fs * up)


def band_levels(ir, fs, nfft=1024):
    H = np.abs(np.fft.rfft(ir, nfft)) ** 2
    f = np.fft.rfftfreq(nfft, 1 / fs)
    out = np.empty(N_BANDS)
    for b in range(N_BANDS):
        m = (f >= BAND_EDGES[b]) & (f < BAND_EDGES[b + 1])
        out[b] = 10 * np.log10(H[m].mean() + 1e-20)
    return out


def itd_us(ir2, fs, up=8, band=(300.0, 1500.0)):
    """Low-frequency ITD from the interaural cross-correlation peak (+ = source on the right).

    Band-passed 300-1500 Hz (fine-structure ITD region); zero-padded so filtering cannot wrap.
    """
    sos = butter(2, band, "band", fs=fs, output="sos")
    n, pad = 2048, 512
    L = np.zeros(n); R = np.zeros(n)
    L[pad:pad + ir2.shape[1]] = ir2[0][: n - pad]
    R[pad:pad + ir2.shape[1]] = ir2[1][: n - pad]
    L = resample(sosfiltfilt(sos, L), n * up)
    R = resample(sosfiltfilt(sos, R), n * up)
    m = int(1e-3 * fs * up)
    X = np.fft.irfft(np.fft.rfft(L) * np.conj(np.fft.rfft(R)))
    lags = np.r_[0:m + 1, -m:0]
    vals = np.r_[X[0:m + 1], X[-m:]]
    return lags[np.argmax(vals)] / (fs * up) * 1e6


def raw_features(ir2, fs):
    itd = itd_us(ir2[:, :512], fs)
    bl = np.stack([band_levels(ir2[c], fs) for c in range(2)])
    ild = bl[0] - bl[1]
    spec = np.diff(bl - bl.mean(axis=1, keepdims=True), axis=1)
    return itd, ild, spec, bl


def grid_features(hrir, max_el=None, min_el=None):
    """Map an HRIR set (dict with ir, az, el, fs) to the regular grid by nearest direction."""
    src = _unit(hrir["az"], hrir["el"])
    AZ, EL = np.meshgrid(GRID_AZ, GRID_EL, indexing="xy")  # (n_el, n_az)
    tgt = _unit(AZ.ravel(), EL.ravel())
    nn = np.argmax(tgt @ src.T, axis=1)
    cache = {}
    itd = np.empty(len(nn)); ild = np.empty((len(nn), N_BANDS)); spec = np.empty((len(nn), 2, N_BANDS - 1))
    lev = np.empty((len(nn), 2, N_BANDS))
    for k, i in enumerate(nn):
        if i not in cache:
            cache[i] = raw_features(hrir["ir"][i], hrir["fs"])
        itd[k], ild[k], spec[k], lev[k] = cache[i]
    ang = np.degrees(np.arccos(np.clip(np.sum(tgt * src[nn], 1), -1, 1)))
    shape = (len(GRID_EL), len(GRID_AZ))
    return dict(itd=itd.reshape(shape), ild=ild.reshape(shape + (N_BANDS,)),
                spec=spec.reshape(shape + (2, N_BANDS - 1)), lev=lev.reshape(shape + (2, N_BANDS)),
                nn_err_deg=ang.reshape(shape), az=GRID_AZ, el=GRID_EL)
