# Psychoacoustics facts for the Marco Polo simulated listener

Scope: a blind user asks "where are my keys?". A head-tracked spatial call plays through AirPods from the item's real 3-D position, rendered with Apple's generic (non-individual) HRTF. The user turns to face the call and walks to the item. Range is indoor, 0.5-6 m.

Compiled 2026-10-14 from on-disk material (notes/psychoacoustics/*, papers/psychoacoustics/*, repos_psychoacoustics/soundscape_src) plus new reads.

Evidence tags:
- [PRIMARY]: read in the source's own text, table or code.
- [ABSTRACT]: abstract only.
- [SECONDARY: X]: reported by source X.
- [FIG]: read by eye from a figure.
- [DERIVED]: my own arithmetic.
- [UNVERIFIED]: from general knowledge; I could not confirm it in a source this session. Treat as a prior, not a fact.

Local copies of new sources:
- papers/psychoacoustics/wenzel1999_latency/paper.pdf
- papers/psychoacoustics/wenzel1998_latency/paper.pdf
- papers/psychoacoustics/majdak2010_oa/fulltext.txt
- papers/psychoacoustics/middlebrooks2015_review/paper.pdf
- papers/psychoacoustics/zhu2023_acoustic_touch/fulltext.txt

Begault 2001, Minnaar 2001 and Oberem 2020 were read from the PDFs already on disk.

---

## 1. Calibration targets for the simulated listener

| Quantity | Value | Condition | Source |
|---|---|---|---|
| Unsigned azimuth error, generic HRTF, static | 21.7° (SD 7.8) | Speech, 3 s, eye level, ±45°/±135°/0°/180°, front-back corrected, 9 naive listeners | Begault, Wenzel & Anderson 2001 JAES, Fig. 4 [PRIMARY] |
| Unsigned azimuth error, generic HRTF, head-tracked | 16.9° (SD 7.8) | Same; 45 ms end-to-end latency | Begault 2001 [PRIMARY] |
| Unsigned azimuth error, individual HRTF | ~18.5° tracked / ~20° static | Same | Begault 2001 Fig. 4 [FIG] |
| Azimuth error vs reverberation | anechoic ~23°; early reflections ~16.5°; full ~18° | Same | Begault 2001 Fig. 3 [PRIMARY/FIG] |
| Elevation error | anechoic 17.6°; reverberant 28.7°; head tracking no effect; upward bias | Speech, targets at 0° elevation | Begault 2001 [PRIMARY] |
| Front-back + back-front reversal rate | static 59% → tracked 28% | Speech, pooled over HRTF type; HRTF type had no significant effect | Begault 2001 [PRIMARY] |
| Externalization | anechoic 40% → with reflections 79%; head tracking no significant effect | Speech | Begault 2001 [PRIMARY] |
| Front-back confusions, nonindividual HRTF | static 27.6% → dynamic 6.8%; another set 22.7% → 6.5% | Broadband noise, 6 listeners | Wenzel 1995/1996 [SECONDARY: Wenzel 1999] |
| Front-back confusions, real sources, static | ~5% "typically" | Free field | [SECONDARY: Wenzel 1999, citing Wenzel 1993] |
| Reversals, nonindividual vs individual HRTF | 31% vs 11% | Noise, static; Wenzel 1993 vs Wightman & Kistler 1989 | [SECONDARY: Begault 2001] |
| Front-back reversals with head motion | front→back 42% → 7%; back→front 13% → 7% | Noise, virtual | Wenzel 1995 [SECONDARY: Begault 2001] |
| Horizontal error, dynamic vs static | static 38.7° vs dynamic 21.2-21.7° (not corrected for reversals) | 11 trained listeners, pulsed noise 3.7 s, 1.5 m, proximal pointing, 14 ms latency | Oberem et al. 2020 [PRIMARY] |
| Gain from individual HRTF on horizontal error | 9.9° static vs 0.2-2.2° dynamic | Same | Oberem 2020 [PRIMARY] |
| Weighted front-back confusions | static 16.5% vs dynamic 6.3-7.1%; individual 7.6% vs nonindividual 10.7% | Same | Oberem 2020 [PRIMARY] |
| Unsigned vertical error | front 19.2°, side 10.3°, back 20.6°; no HRTF or dynamic effect | Same | Oberem 2020 [PRIMARY] |
| In-head localization | static 6.4% vs dynamic 0.5-0.7% | Same | Oberem 2020 [PRIMARY] |
| Lateral RMS / local polar RMS / quadrant error, own-ear | 14.5° / 28.7° / 7.7% | Trained listeners, head pointing, dark | Middlebrooks 1999 Table I [SECONDARY: Majdak 2010 Table 4] |
| Same metrics, Majdak individual-HRTF virtual | lateral 14.4-18.6°; local polar 37-38°; quadrant 19-22% (naive); 12.3°/31-33°/8-11% after training | Head or manual pointing | Majdak et al. 2010 Table 4 [PRIMARY] |
| Training effect | naive quadrant error 27.5% → 18.3% after ~400 trials; lateral precision 17.1° → 15.4° | Same | Majdak 2010 Table 1 [PRIMARY] |
| Median-plane (front/back/up) identification errors | real life 9.7%; best human-head recording 33%; artificial heads 38-54% (KEMAR 50.5%, KU100 43%) | 19-speaker room, head still, speech + noise, 20 listeners | Minnaar et al. 2001 Table 1 [PRIMARY] |
| Out-of-cone (lateral) errors | real 0.3%; heads 2-6% | Same | Minnaar 2001 [PRIMARY] |
| Distance identification errors | ~10% real vs 13-17% binaural; head type not significant | 1, 1.7, 2.9, 5 m speakers | Minnaar 2001 [PRIMARY] |
| Learning over 5 days | real-life median-plane errors 15.5% → 9.6% | Same | Minnaar 2001 Table 3 [PRIMARY] |
| Latency tolerance (localization) | Front-back confusions 5.2-8.8%, not affected at 33.8/100/250/500 ms; error angle 26.2° → 36.3° (only 500 ms significant) | Individual HRTF, 8 s noise, 5 listeners | Wenzel 1999 AES16 [PRIMARY] |
| Latency noticeability | Ratings ~minimum at 34 and 100 ms; noticed from ~250 ms | Same | Wenzel 1999 [PRIMARY] |
| Latency harming localization | >73 ms raises errors for brief sounds and response time for continuous sounds; best detection threshold 60-70 ms (25 ms lower with a reference tone); <30 ms hard to detect | Low-latency virtual audio display | Brungart et al. 2006 [ABSTRACT] |
| Earlier latency/update threshold | Degradation from 96 ms latency or <10 Hz update; 13° HRTF grid had little impact | Gun-pointing, ~1.75 s trials | Sandvad 1996 [SECONDARY: Wenzel 1999] |
| Peak head yaw velocity during localization | ~175°/s bursts | Free head motion, virtual noise | Wenzel 1999 [PRIMARY] |
| Yaw excursion when encouraged to move | mean max −86° / +95° yaw; pitch ±15°; roll −5/+14° | 8 s stimulus | Wenzel 1999 [PRIMARY] |
| Head-orient onset latency | 0.4 s (NH) / 0.6 s (HI) | Free field speech, ±75° | Brimijoin et al. 2010 [PRIMARY] (notes q3) |
| Time to settle within ±3° | 0.9 s NH / 1.2 s HI | Same | Brimijoin 2010 [PRIMARY] |
| Peak yaw velocity vs jump | ~50°/s @30°; ~120°/s @60° (example); ~150°/s @105° | Sigmoidal profile, peak at mid-movement | Brimijoin 2010 [PRIMARY] |
| Undershoot | Grows with eccentricity; e.g. 9° at a 60° jump (example listener) | Same | Brimijoin 2010 [PRIMARY] |
| Final head-orientation error | 7.7° mean absolute; signed −1.2°; individual bias −14 to +10° | Loudspeaker talker in simulated room, no pinna cues (BTE mics) | Whitmer et al. 2022 [PRIMARY] |
| HRTF grid resolution | 1°, 2.5° and 5° equal for accuracy; 5° gives audible switching artifacts | Dynamic | Oberem 2020 [PRIMARY] |
| MAA, frontal | ~1° | Tones ≤1 kHz, free field | Mills 1958 [UNVERIFIED value]; "highest acuity" at front [SECONDARY: Middlebrooks 2015] |
| MAA vs azimuth | Roughly 1-2° @0°, a few degrees @45-60°, large and frequency-dependent near 75-90° | Same | Mills 1958 [UNVERIFIED shape] |
| Poorly localized band | ~2-4 kHz tones: "neither ITD nor ILD reliable" | Free field | Middlebrooks 2015 review [PRIMARY] |
| Spectral (front/back, elevation) cue band | ≥ ~4 kHz needed | — | Middlebrooks 2015 [PRIMARY] |
| ITD dominance | Below ~1.5 kHz; ITD threshold 10-20 µs | — | Middlebrooks 2015 [PRIMARY] |
| ILD threshold | ~1 dB | — | Middlebrooks 2015 [PRIMARY] |
| Distance bias crossover | Underestimate >1.5 m, overestimate <1.5 m | — | Middlebrooks 2015 [PRIMARY]; Kolarik 2016 (best ~1 m) [PRIMARY] |
| Level vs distance | −6 dB/doubling anechoic; ~4 dB/doubling small room; reverberant ~1 dB | — | Kolarik 2016 [PRIMARY] |
| Distance discrimination, blind | ~0.8 m at 2 m; ~1.5 m at 5 m | — | Kolarik 2013b [SECONDARY: Kolarik 2016] |
| Beacon rate in navigation studies | 250 ms sound + 1 s silence (~0.8 Hz), faster on approach | Walker & Lindsay 2006 [PRIMARY]; Tran 2000 best: sonar at 1.1 rep/s [SECONDARY: Walker & Lindsay 2003] |
| Spatial speech call rate | 72 per minute (0.83 s period); fastest and best-rated display | 15 blind users, GPS | Loomis et al. 2005 [PRIMARY] |
| Blind walking speed with guidance | 0.56 m/s mean (cane, 50 m route, 6 turns); 6 fastest ~0.7 m/s | Loomis 2005 [PRIMARY] |
| Walking speed in VR beacon studies | 1.2 m/s fixed (joystick) | Walker & Lindsay 2006 [PRIMARY] |
| Capture radius | 1.5 m best outdoors; 0.5 m → overshoot and "hunting" | Walker & Lindsay 2006 [PRIMARY] |
| Soundscape beacon cones (default "Current") | A+ ±15°; A 15-55°; B 55-125°; Behind 125-180° | Microsoft Soundscape source [PRIMARY code] |
| Soundscape beacon timing | Continuous loop; 2.416 s phrase of 6 beats (0.403 s/beat); onset IOI A+ ≈0.61 s, A ≈0.60 s, B ≈1.0 s, Behind 1 per 2.4 s | Code + WAV analysis [PRIMARY/DERIVED] |
| Soundscape beacon spectrum | Near-tonal; A+ centroid 2.7 kHz, A/B ~2.35 kHz, Behind ~1.17 kHz; energy >4 kHz ≈0 | WAV analysis csv [DERIVED] |
| Soundscape haptic lock-on | Full audio within 15° of target, linear to 0 at 30°; heavy tap every 0.5 s while inside window (pulse beacon: ±15° window); `.error` haptic when sweeping across the bearing; long-focus after 1.0 s | Code [PRIMARY] |
| Clock-face reach task | Correct-item success 90.7% ± 11.7 (Clock) vs 85% (co-located speakers) vs 81.7% (wearable sonification) | 7 BLV, seated, 2-3 items on a table | Zhu et al. 2023 PLoS One [PRIMARY] |
| Veering mechanism | Blind ≈ blindfolded trajectories; model has 3 motor-error sources (initial orientation, constant step bias, variable step error, the last dominant) | Kallie, Schrater & Legge 2007 [ABSTRACT] |

---

## 2. Design implications

- **Head tracking matters more than HRTF individualization; plan for a generic HRTF.** Head tracking cut reversals 59% → 28% (speech) and 27.6% → 6.8% (noise). With head tracking, individual HRTFs add only 0.2-2° of azimuth accuracy. Simulator prior: generic HRTF, static, has 20-40% front/back flips. Once the listener has turned the head by more than ~20-30°, flips drop to ~6-10%.
- **Head tracking does not fix elevation.** Elevation error stays at 17-29° regardless of tracking, with an upward bias. Keys are usually below eye level (on a table, floor or couch).
  - Model elevation as nearly uninformative from the HRTF.
  - Carry height with speech ("on the table, waist height") or an explicit cue. Possible cues: pitch, or a "low" sound variant. Pitch-height mapping is [UNVERIFIED] here.
- **"Turn until dead ahead" exploits the best part of the auditory field.** MAA is ~1° in front and spatial acuity is highest at the frontal midline (Mills 1958; Middlebrooks 2015).
  - Realistic end-of-turn error is ~8° (Whitmer 2022, real sources).
  - With a generic HRTF, use 10-20° (Begault, tracked: 16.9°, absolute judgment).
  - Undershoot grows with target eccentricity, so expect a second, corrective turn for targets beyond 60°.
- **Model a sigmoid head turn.** Onset ~0.4 s. Peak velocity scales with the angle of the turn: ~50°/s at 30°, ~150°/s at 105°, bursts up to 175°/s. Settling within ±3° takes ~0.9 s.
  - So a 90° turn takes ~1.3 s.
  - With a 1 Hz call, the user gets only 1-2 calls during the turn, so dynamic-cue sampling is sparse.
- **Latency of 30-150 ms barely affects the localization outcome.** Front-back resolution survived 500 ms in Wenzel 1999. But Brungart 2006 found that errors for brief sounds rise beyond ~73 ms, and response time rises for continuous sounds.
  - AirPods head-tracking latency is unknown here; measure it.
  - Simulator: delay the rendered source angle by L. For brief calls, add ~0.02-0.04° of error per ms above 70 ms. That slope is [DERIVED] from Wenzel's 26° → 36° over 34 → 500 ms, taken as a linear lower bound.
- **Calls need duration during head motion.** Oberem notes that head movements are "hardly witnessed" for sounds under 200 ms and best observed at ≥2 s (citing Thurlow & Mergener 1970).
  - A 250 ms call once per second works when the user turns between calls and compares successive snapshots. Brief calls plus latency is exactly the case Brungart found most fragile.
  - Prefer a ≥300-500 ms broadband call, or a looping beacon whose timbre changes on-axis (Soundscape's approach).
- **Make the call broadband with energy above 4 kHz.** Front/back and elevation cues need ≥4 kHz, and 2-4 kHz tones are the worst-localized band.
  - Soundscape's tonal 1.2-3 kHz beacons rely on an explicit on-axis asset swap, not HRTF cues. Copy that idea: add a distinct "dead ahead" variant within ±15°.
  - Walker & Lindsay found broadband noise/sonar marginally better than tones.
- **Add early reflections.** They doubled externalization (40% → 79%) and cut azimuth error by ~5°, at the cost of more elevation error. For AirPods, a mild room model is worth it.
- **Distance must be coded explicitly.**
  - Absolute auditory distance is compressed and biased (crossover ~1-1.5 m).
  - Soundscape renders beacons at a fixed 1 m, with no level-based distance cue.
  - Use tempo-as-proximity (Walker & Lindsay), a speech distance (Loomis: spoken "24" at 72/min was best), or a near-field ILD only under 1 m.
- **The final approach needs a capture/arrival rule.**
  - Small capture radii cause overshoot and hunting. Indoors, use ~0.3-0.5 m, then switch to a "within reach" mode (speech plus height, haptic).
  - Blind walking with guidance runs ~0.5-0.7 m/s, so 6 m takes ~10 s. Veering is a random walk in step direction, so re-aim every 1-2 m.
- **Use haptic lock-on as a confirmation, not as the primary search cue.** Soundscape's pattern was: full volume within ±15°, fading to silence at 30°, a tap every 0.5 s while inside the window, and a distinct tick when sweeping across the bearing. This maps directly to a "lock" event in the simulator.
- **Expect large individual differences and fast learning.** Learning curves: Majdak, quadrant error 27.5% → 18.3% in ~400 trials; Minnaar, 5-day improvement. Simulate a per-user bias of ±10-15° (Whitmer: −14 to +10°) and a learning term.

---

## 3. Details by question

### Q1. Static localization with non-individual HRTFs

**Wenzel, Arruda, Kistler & Wightman 1993, JASA 94:111** [ABSTRACT]
- Wideband noise. Virtual sources used a "good localizer's" HRTFs, compared against free field.
- "When confusions were resolved, localization of virtual sources was quite accurate and comparable to the free-field sources for 12 of the 16 subjects." Two listeners had poor elevation in both conditions, and two had degraded virtual elevation.
- Front-back and up-down confusions "increased significantly for virtual sources".
- Interpretation: interaural cues are robust; spectral cues are distorted.
- Numbers via secondary sources:
  - ~31% reversals vs 11% for individualized (Begault 2001 citing Wenzel 1993 vs Wightman & Kistler 1989).
  - Real-source static confusion "on the order of 5%" (Wenzel 1999 citing Wenzel 1993).
  - Commonly cited medians of ~19% free field vs ~31% virtual front-back [UNVERIFIED split].

**Middlebrooks 1999, JASA 106:1493 (virtual localization improved by scaling)** [ABSTRACT + SECONDARY]
- Own-ear errors are lowest. Other-ear errors grow with the inter-subject DTF mismatch.
- Other-ear features lower in frequency than the listener's: low-front targets are heard low-rear, and high-rear targets high-front.
- Features higher in frequency: elevation is biased upward.
- Frequency scaling "more than halved the penalty".
- Own-ear Table I [SECONDARY: Majdak 2010]: lateral bias 3.1°; lateral RMS 14.5° ± 2.2; local polar RMS 28.7° ± 4.7; elevation bias 10.2°; quadrant 7.7% ± 8.0.
- Other-ear numbers were not obtained (paywalled). Prior: roughly 2× quadrant errors and +10-15° polar error [UNVERIFIED].

**Majdak, Goupell & Laback 2010, APP 72:454** (individual HRTF, virtual) [PRIMARY]
- Naive listeners: lateral precision 18°, polar precision 23.3°, quadrant error ~30% (chance 48%).
- After training: 12.2° and 19.8° (Table 1/4 values above).
- Elevated targets were near chance for polar and quadrant errors; eye-level targets were much better.
- For comparison: Begault 2001 quadrant error 59% (static) and Bronkhorst 1995 28% (naive).

**Møller et al. 1996 / Minnaar et al. 2001** [PRIMARY from Minnaar]
- Individual binaural recordings show no significant difference from real life (Møller 1996, as summarized by Minnaar).
- Nonindividual recordings are poorer. A well-chosen human head is better than any artificial head: 60% of 30 human heads beat the best artificial head.
- Minnaar Table 1, median-plane errors: real 9.7%; AVH 33.0%; DOL 33.2%; VALDEMAR 38.1%; ITA 40.0%; KU100 43.0%; MK1 50.3%; KEMAR 50.5%; 4100 52.4%; HMS II 53.7%.
- Left/right is "nearly always correctly perceived" (ITD dominance).
- Speech and white noise did not differ.

**Begault et al. 2001**
- Full data are in the table above.
- Static generic-HRTF speech: azimuth error 21.7° and reversals ~59%. The authors note this is higher than their earlier 37% for speech.
- Per-subject biases: e.g. elevation mean 42° for one subject vs 0.3° for another.
- Individual HRTFs gave no significant benefit for speech, plausibly because speech energy is dominated by low frequencies (long-term average peak at 500 Hz).

**Wightman & Kistler 1999, JASA 105:2841** [ABSTRACT]
- Front-back confusions in the head-restricted condition "nearly disappeared" when head movement was encouraged.
- With the head fixed, confusions disappeared only when the listener moved the source, not when the experimenter did.
- Implication: self-generated relative motion is what resolves the ambiguity.
- Wightman & Kistler 1989 numbers were not re-verified. Their individualized virtual and free-field localization were nearly equivalent [SECONDARY: Oberem 2020].

**Static-error model for the simulator** [DERIVED]
1. Lateral angle ~ N(true, σ). σ is ≈10-15° near the front and ≈15-20° lateral, plus a per-user bias.
2. Polar angle: with probability p_flip (0.25-0.35 static generic; 0.06-0.10 after a head turn), mirror about the interaural axis. Otherwise apply N(0, 25-35°).
3. Elevation: N(+10° bias, 20-30°).

### Q2. Head movement, head tracking and latency

- **Confusion reductions:** Begault 59 → 28%; Wenzel 27.6 → 6.8%; Oberem 16.5 → 6.3%.
  - After removing reversal trials, static and dynamic horizontal error do not differ (Oberem: "RepMeth F<1"). The dynamic benefit is almost entirely front/back resolution.
- **What head movement does not fix:** elevation (Begault; Oberem) and Begault-style absolute azimuth accuracy beyond the interaction effect.
- **Head-movement amount vs accuracy:** Begault Fig. 13 shows r = −0.75 between mean yaw and azimuth error. The best localizer moved the most, and the worst three moved less than their average error.
  - The 3-s stimuli may have limited the benefit.
- **Latency: Wenzel 1999** [PRIMARY]
  - Front-back confusions 5.2-8.8% at every latency (n.s.).
  - Up-down confusions 11.3 → 21.3% (only 500 ms significant).
  - Externalization 96-98%.
  - Error angle 26.2 → 36.3°.
  - Listeners "ignore latency during active localization" even though the source visibly "slews".
  - The earlier system latency was 54.3 ± 8.8 ms (35-75 ms). From the minimum audible movement angle (MAMA), the inferred minimum perceptible latency is ~69 ms at 180°/s.
- **Latency: Brungart et al. 2006** [ABSTRACT] — see the table. Recommendation: under 60 ms is adequate; under 30 ms is hard to detect.
- **Lindau 2009 latency-detection threshold** — not retrieved. The prior is that the detection threshold is ~50-75 ms for dynamic binaural synthesis [UNVERIFIED].
- **Effect of ~150-300 ms latency** [DERIVED from Wenzel and Brungart]
  - Little change in front/back resolution for long sounds.
  - Several degrees more error, rising with latency.
  - Longer settle and response times, because the user overshoots while the image lags.
  - Noticeable lag from ~250 ms.
  - For a 250 ms call, a 200 ms lag means the image moves with the head for most of the call. Use longer calls or a continuous loop.

### Q3. MAA, head pointing, head-turn dynamics

- **Mills 1958:** MAA is ~1° straight ahead for low-frequency tones, increases with azimuth, and becomes very large or unmeasurable near 90° for mid frequencies. Numeric curve [UNVERIFIED].
  - Middlebrooks 2015 [PRIMARY] confirms highest acuity at the front (citing Mills) and the 2-4 kHz error region.
- **Head-pointing end error:** 7.7° (Whitmer 2022). Errors increase with target angle (Brimijoin 2014). Brimijoin 2010 undershoot grows with eccentricity. Misorientation (initial turn the wrong way by >3°) is used as a metric.
- **Dynamics:** see the table (Brimijoin 2010; Wenzel 1999: 175°/s bursts over ~1.2 s). Pitch varies only ~2° during yaw turns (Brimijoin 2010). Users mostly yaw (Wenzel 1999).

### Q4. Beacon design

- **Walker & Lindsay 2003/2006** (notes q4q5): 250 ms beacons, 1 s silence, tempo rising with proximity. Capture radius matters more than timbre. Path efficiency 75 → 99% over 3 maps. Non-individual HRTF plus a head tracker.
- **Tran, Letowski & Abouchacra 2000** [SECONDARY: Walker & Lindsay 2003, 2005]:
  - Wide-band non-speech beacon with balanced low/high energy.
  - Sonar best overall at 1.1 repetitions/s.
  - Frontal accuracy 7-15°.
  - Speech "most likely not optimal" for localization.
  - Quality ratings correlated with localization performance.
  - (Loomis 2005 found spatialized speech fastest for blind users, partly because it carried distance.)
- **Continuous vs intermittent:**
  - Loomis 2005: users complained about the "continuous presence of tones". The intermittent spatial speech at 72/min was preferred.
  - Soundscape uses a continuous rhythmic loop whose content changes with the off-axis angle.
  - Wenzel 1999 / Oberem 2020 used long (3.7-8 s) stimuli to allow head-motion sampling.
  - Compromise [DERIVED]: rhythmic pulses at ~0.4-0.6 s spacing while the user is searching or turning, sparser when on-axis and walking.
- **Microsoft Soundscape beacon behavior** [PRIMARY: repos_psychoacoustics/soundscape_src]
  - **Asset selector by angle** (Audio_Protocols_DynamicAudioEngineAsset.swift).
    - Two-region (Classic): on-axis ±22.5°.
    - Three-region: A+ ±15°; A 15-125°; Behind 125-235°.
    - Four-region (default V2 "Current"): A+ ±15°; A 15-55°; B 55-125°; Behind 125-235°.
    - No heading available: Behind (4-region) or off-axis (2-region) asset, and audio is "dimmed" (rendered at 5 m instead of 1 m).
  - **Timing.** Assets loop (`.loops`). A switch is quantized to the next beat (beatsInPhrase 6; phrase 2.416 s; 0.403 s/beat). Classic has 2 beats of 0.588 s.
    - Measured onset IOI from soundscape_beacon_wav_analysis.csv: Current A+ 0.61 s, A 0.60 s, B 1.0 s, Behind a single event per 2.4 s phrase.
    - So pulse rate falls and pitch drops (~2.35 → 1.17 kHz) as the target moves behind.
    - "Slow" and "Very slow" variants use 12 and 18 beats per phrase.
  - **Spatial rendering.** HRTF via AVAudioEnvironmentNode.
    - Source position = bearing at `envRenderingDistance` = 1.0 m (constant, no distance attenuation by real range).
    - referenceDistance 2.0. Default beacon volume 0.75.
  - **Proximity.**
    - ProximityBeacon hum: "near" asset when <20 m, "far" at 20-30 m, silent beyond.
    - Geofence: enter vicinity 15 m, leave 30 m.
    - Distance callouts throttled to ≥5 s and ≥50 m (MotionActivityUpdateFilter).
    - These are GPS/outdoor scales. For 0.5-6 m indoors, scale down by ~10-30×.
  - **Haptic beacons** (wand / pulse).
    - Target windows: 60° (wand) and 30° (pulse; 110° if the "A haptics" variant is enabled).
    - Audio loop volume 1.0 within 15° of the bearing, linear to 0 at 30°.
    - On focus: `.impactHeavy` every 0.5 s. Variant: heavy within ±15°, light at 15-50°.
    - Crossing the exact bearing triggers an `.error` haptic ("tick").
    - Long-focus timer 1.0 s.
    - Audio plays only when the phone is held flat.

### Q5. Supernormal cues and spectral enhancement

**Shinn-Cunningham, Durlach & Held 1998, JASA I and II** [ABSTRACT]
- **Method:** HRTF-to-direction mapping was remapped to exaggerate spatial differences (the "supernormal" transformation was nonlinear, magnifying differences near the front). Subjects were trained with feedback.
- **Part I:**
  - "Response bias decreases substantially with training" but adaptation is incomplete.
  - Resolution depends on the stimulus and the adaptation state. My reading of the abstract is that resolution first increases with exaggerated cues, then falls as subjects adapt [UNVERIFIED direction/magnitude].
- **Part II:**
  - Mean response is roughly proportional to the normal position of the cues.
  - The best-fit slope changes exponentially with time toward a linear approximation of the transform. Subjects "cannot adapt to a nonlinear transformation".
  - The adaptation rate is independent of the transform; the asymptote depends on its strength.
- **Implication [DERIVED]:**
  - Exaggerating azimuth near the front (e.g. render an angle θ as k·θ with k ≈ 1.5-2 inside ±30°) should sharpen "dead-ahead" detection immediately.
  - It introduces a bias that users partially adapt to, linearly.
  - The null at 0° stays put, so "face it" still lands on the true bearing. A gain k>1 near 0° makes small residual offsets sound larger, so users should keep correcting until they are closer to dead ahead. The risk is over-correction or oscillation around the null.
  - Simulate it as a perceived angle k·θ (|θ| < 30°) with k decaying toward 1 over ~tens of trials.

**Spectral enhancement for front/back**
- No primary source retrieved this session [UNVERIFIED].
- Physical basis [PRIMARY: Middlebrooks 2015]: front/back cues live in ≥4 kHz pinna spectra, and narrowband sounds are mislocalized by center frequency (Blauert's directional bands).
- Practical cheap trick [DERIVED]: make the behind variant spectrally distinct (dull/low-passed, as Soundscape's Behind asset at ~1.17 kHz effectively does). Optionally boost 6-10 kHz for front sources. This turns a perceptual cue into a categorical one.

### Q6. Distance; elevation-to-pitch

**Distance** (notes q6q7, Kolarik 2016)
- Compressive power function, a<1. Best accuracy around 1 m.
- Level is a relative cue only.
- DRR is the most reliable cue in rooms (Middlebrooks 2015).
- Near-field ILD helps under ~1 m.
- Minnaar: distance errors were the same for real and binaural playback, so room cues dominate.
- Wenzel 1999: externalized distance judgments averaged ~1-2 ft with individual HRTFs, i.e. compressed.

**Elevation-to-pitch**
- Higher pitch is heard as higher in space (Pratt 1930; Parise, Knorre & Ernst 2014 PNAS link this to natural scene statistics and pinna filtering).
- Not retrieved due to rate limiting [UNVERIFIED]. Use it only as a learned or explicit code.
- Note that elevation error is 17-29° even with head tracking.

### Q7. O&M conventions and blind locomotion

- **Clock face:** egocentric clock positions relative to the body (12 o'clock = straight ahead). Zhu 2023 used it as an "idealized" verbal condition: 90.7% correct-item reach for BLV users, the best of the three conditions.
  - In O&M, clock face is also used for table/plate layouts (relative to the person, or to the plate) [UNVERIFIED as formal convention].
- **Systematic search for a dropped or near object** [UNVERIFIED, standard O&M teaching]:
  - Listen for the drop, face it, squat (avoid bending at the waist; use upper-body protective technique).
  - Hand search outward from the body in a pattern: small circles widening outward, or a grid / parallel sweeps.
  - Tabletop: hands "trailing" the surface from the near edge outward.
  - Simulator implication: once within reach (~0.5 m), search time scales with area / (hand sweep rate). Height cueing matters.
- **Walking speed:**
  - 0.56 m/s mean with cane and GPS guidance, 0.7 m/s for the fastest six (Loomis 2005) [PRIMARY].
  - The preferred walking speed (PWS) methodology for VI adults exists: 20 m corridor; sighted-guide and solo PWS do not differ (Soong et al. 2000) [ABSTRACT].
  - Typical PWS for VI adults is ~1.0-1.2 m/s unguided-open [UNVERIFIED]. Indoors with an uncertain target, use ~0.4-0.7 m/s.
- **Veering:**
  - Kallie, Schrater & Legge 2007 [ABSTRACT]: blind and blindfolded walkers veer alike. Veering is explained by initial orientation error, a constant step bias, and dominant variable step error (a random walk).
  - Cheval-like study (PLoS One 2012) [ABSTRACT]: 50% of trajectories ended left, 39% right, 11% straight.
  - A blindfolded vestibular-noise study reports veer angles of ~1-2° changes [ABSTRACT].
  - Simulator: heading random walk with per-step SD ~2-4° and bias ~0-2°/step [UNVERIFIED magnitude]. Over 6 m (~9 steps), lateral drift is ~0.2-0.5 m, which favors re-aiming mid-route.

### Q8. Speech vs spatial vs haptic guidance

(Notes q8q9.) Loomis et al. 2005, 15 blind participants:
- Spatialized speech (72/min) was fastest: ~94 s per 50 m route vs HPI tone ~126 s.
- It was best-rated (~8/10). Distance traveled did not differ.
- Continuous tones were disliked. Hand-held pointing (HPI) is faster for scanning than body turning.
- Headphones blocking ambient sound was a common complaint. AirPods transparency mode mitigates this; Walker & Lindsay 2005 report users would not give up environmental hearing.
- Zhu 2023: verbal clock description ≥ spatial sonification for the final reach (90.7% vs 81.7%).

Implication: use spatial audio for the bearing, speech for distance and height, and haptic for confirmation.

### Q9. Haptic lock-on cues

- **Soundscape implementation** (Q4 above) is the concrete reference:
  - ±15° full-strength window.
  - 0.5 s heavy tap cadence inside the window.
  - Bearing-crossing tick.
  - Optional graded light tap at 15-50°.
- **Teleguidance smart-cane study** (Chaudary et al. 2021, VR journal) [ABSTRACT]: blind users preferred two actuators (left/right). Partially sighted users preferred a single actuator with patterns.
- **Haptic belt vs smartwatch vs visual compass** (Tkacz 2024 thesis) [ABSTRACT]: haptics gave more environmental awareness but lower precision than a visual compass.
- **Simulator implication [DERIVED]:** model haptic lock as a binary detector with a window W (15-30° half-width) and ~0.5 s sampling latency. The user stops turning once the cue is "on" and continues ~0.5·ω·Δt past the edge, where ω is the turn speed. That argues for a narrow window plus a crossing tick.

---

## 4. Evidence on "repeat a call ~once per second and turn until it's dead ahead"

**For**
1. Closest analogues used this rhythm and worked with non-individual HRTFs plus head tracking:
   - Walker & Lindsay 2006: 250 ms + 1 s gap, 99% path efficiency after practice.
   - Tran 2000: sonar at 1.1/s best.
   - Loomis 2005: spatial speech every 0.83 s was fastest and best-liked by blind users.
2. Turning resolves the main failure of generic HRTFs: front/back flips go 59 → 28% (speech), 27.6 → 6.8% and 16.5 → 6.3% (noise). Dynamic reproduction erases most of the individual-HRTF advantage (Oberem; Begault).
3. "Dead ahead" is where auditory acuity is best (MAA ~1°; Middlebrooks 2015). End-of-turn head-pointing error is ~8°.
4. Localization tolerates even 250-500 ms latency in front/back terms (Wenzel 1999).

**Against / caveats**
1. Short calls are poor for dynamic cues:
   - Head motion is rare for sounds under 200 ms (Thurlow, via Oberem).
   - Brungart 2006 found brief sounds are the ones degraded by latency over ~73 ms.
   - A 1 Hz, 250 ms call leaves the user "blind" 75% of a ~1-1.3 s head turn. Expect overshoot or undershoot and a second correction for targets beyond 60° (Brimijoin undershoot).
2. Elevation is not improved by turning (error 17-29°, upward bias), and indoor items sit low. Beyond ~1 m, a 15-20° azimuth error means 0.3-2 m lateral miss at 1-6 m [DERIVED]. The final approach needs speech, height and haptic cues.
3. Tonal or narrow calls (like Soundscape's ~2.35 kHz beacons) lack ≥4 kHz front/back cues. Soundscape itself did not trust HRTF alone: it adds an explicit ±15° on-axis sound variant and a behind variant.
4. Continuous tones annoyed blind users (Loomis 2005). Headphones that block ambient sound are disliked.

**Net:** keep the ~1 Hz call, but:
- make it broadband, ≥300-500 ms (or ~2 Hz pulses while the head is moving);
- add a categorical "on-axis" (±10-15°) timbre or haptic confirmation;
- code distance and height explicitly.
