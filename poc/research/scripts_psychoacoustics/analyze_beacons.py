"""Analyze Soundscape beacon WAVs: duration, beat period, onsets, duty cycle, spectrum.
Usage: python -I analyze_beacons.py <wav_dir>
Reads WAV data only (no code from the data dir is executed)."""
import sys, os, glob
import numpy as np
import soundfile as sf

BEATS = {  # from DynamicAudioEngineAssets.swift (beatsInPhrase)
    'Classic': 2, 'Current': 6, 'Tactile': 6, 'Flare': 6, 'Shimmer': 6, 'Ping': 6,
    'Drop': 6, 'Signal': 6, 'Signal_Slow': 12, 'Signal_Very_Slow': 18,
    'Mallet': 6, 'Mallet_Slow': 12, 'Mallet_Very_Slow': 18, 'Proximity': 6, 'Route': 6,
}

def family(name):
    base = name.rsplit('_', 1)[0]
    for k in sorted(BEATS, key=len, reverse=True):
        if base == k or base.startswith(k + '_') or base == k.replace('_', ' '):
            return k
    return base

def analyze(path):
    x, sr = sf.read(path, always_2d=True)
    x = x.mean(axis=1)
    dur = len(x) / sr
    peak = np.max(np.abs(x)) + 1e-12
    # 5 ms RMS envelope
    hop = int(0.005 * sr)
    n = len(x) // hop
    env = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-12
    env_db = 20 * np.log10(env / env.max())
    duty_20 = np.mean(env_db > -20)
    duty_30 = np.mean(env_db > -30)
    # onsets: rising crossings of -20 dB after >=40 ms below -26 dB (simple hysteresis)
    onsets = []
    below = True
    below_count = 100
    for i, v in enumerate(env_db):
        if v < -26:
            below_count += 1
            if below_count * 5 >= 40:
                below = True
        else:
            below_count = 0
        if below and v > -20:
            onsets.append(i * hop / sr)
            below = False
    ioi = np.diff(onsets) if len(onsets) > 1 else np.array([])
    # event durations above -20 dB
    events = []
    on = False
    for i, v in enumerate(env_db):
        if v > -20 and not on:
            on = True; s = i
        elif v <= -20 and on:
            on = False; events.append((i - s) * hop / sr)
    if on:
        events.append((len(env_db) - s) * hop / sr)
    # spectrum
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sr)
    tot = X.sum() + 1e-20
    cen = (f * X).sum() / tot
    c = np.cumsum(X) / tot
    f10 = f[np.searchsorted(c, 0.10)]; f50 = f[np.searchsorted(c, 0.50)]; f90 = f[np.searchsorted(c, 0.90)]
    frac_above_4k = X[f >= 4000].sum() / tot
    frac_above_8k = X[f >= 8000].sum() / tot
    peakf = f[np.argmax(X)]
    fam = family(os.path.basename(path)[:-4])
    beats = BEATS.get(fam)
    return dict(name=os.path.basename(path), sr=sr, dur=dur, fam=fam, beats=beats,
                beat=(dur / beats if beats else None), n_onsets=len(onsets),
                ioi_med=(float(np.median(ioi)) if len(ioi) else None),
                ev_med=(float(np.median(events)) if events else None), duty20=duty_20, duty30=duty_30,
                cen=cen, f10=f10, f50=f50, f90=f90, a4k=frac_above_4k, a8k=frac_above_8k, peakf=peakf)

def main():
    d = sys.argv[1]
    print('name,sr,dur_s,beats,beat_s,n_onsets,median_IOI_s,median_event_s(>-20dB),duty>-20dB,duty>-30dB,centroid_Hz,f10_Hz,f50_Hz,f90_Hz,energy>4k,energy>8k,peak_Hz')
    for p in sorted(glob.glob(os.path.join(d, '*.wav'))):
        r = analyze(p)
        fmt = lambda v, s='{:.3f}': ('' if v is None else s.format(v))
        print(','.join([r['name'], str(r['sr']), fmt(r['dur']), str(r['beats']), fmt(r['beat']), str(r['n_onsets']),
                        fmt(r['ioi_med']), fmt(r['ev_med']), fmt(r['duty20'], '{:.2f}'), fmt(r['duty30'], '{:.2f}'),
                        fmt(r['cen'], '{:.0f}'), fmt(r['f10'], '{:.0f}'), fmt(r['f50'], '{:.0f}'), fmt(r['f90'], '{:.0f}'),
                        fmt(r['a4k'], '{:.3f}'), fmt(r['a8k'], '{:.3f}'), fmt(r['peakf'], '{:.0f}')]))

if __name__ == '__main__':
    main()
