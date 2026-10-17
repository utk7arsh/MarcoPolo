# Q3 notes: MAA vs azimuth, head-pointing accuracy, head-turn kinematics, audio-cued search time

Tags: [PRIMARY] read in paper text/table; [ABSTRACT] abstract only; [SECONDARY: src] cited by another source; [MEMORY-UNVERIFIED] not verified.
Figure-read values marked "approx, read from Fig. N".

## Brimijoin, McShefferty & Akeroyd 2010, "Auditory and visual orienting responses in listeners with and without hearing-impairment", JASA 127(6):3678-3688. doi:10.1121/1.3409488
URL (author manuscript, full text): https://pmc.ncbi.nlm.nih.gov/articles/PMC4338612/ (read via NCBI E-utilities efetch XML; local copy papers/psychoacoustics/brimijoin2010_orienting/fulltext.txt)
Condition: free field, 24-speaker ring r=0.9 m, targets -75..+75 deg (15-deg steps), jumps 30-150 deg (analyzed <=105), ASL sentences ~1.3 s, 65-75 dB SPL, ISI 2.5-3.5 s; listeners did NOT recentre between trials; instructed "orient their heads as quickly as was comfortable"; eyes-closed/blindfolded audio condition; 17 normal-hearing (NH, mean age 29) + 14 hearing-impaired (HI, mean 58); Vicon 100 Hz; yaw only. Initial latency = time to move +-3 deg; fixation latency = time to get within +-3 deg of final resting position.
- Initial (movement-onset) latency to auditory targets: NH 0.4 s, HI 0.6 s (visual: NH 0.3 s, HI 0.4 s). No effect of jump size. [PRIMARY] Quote: "On average, the initial latency of normal-hearing listeners in response to auditory targets was 0.4 seconds, while that of hearing-impaired listeners was 0.6 seconds."
- Fixation latency (to within +-3 deg of final position): NH 0.9 s, HI 1.2 s (visual NH 0.8 s, HI 1.0 s). [PRIMARY] Quote: "the fixation latency of normal-hearing listeners in response to auditory targets was 0.9 seconds, while that of hearing-impaired listeners was 1.2 seconds."
- Initial latency grows ~10 ms per dB of hearing loss. [PRIMARY] (Discussion C)
- Peak yaw velocity vs jump size: ~50 deg/s for +-30 deg jumps; ~150 deg/s (NH) / ~130 deg/s (HI) for +-105 deg jumps; not sig. different between groups; visual slightly (n.s.) faster. [PRIMARY] Quote: "Small jump sizes (+-30 deg) resulted in peak velocities of roughly 50 deg/sec ... The largest jump sizes (+-105 deg) resulted in peak velocities of approximately +-150 deg/sec in normal-hearing and about +-130 deg/sec in hearing-impaired listeners". Abstract: "Peak velocity reached roughly 140 degrees per second in both groups".
- Trajectory shape: "The stereotypical movement trajectory was sigmoidal in shape, reaching peak velocity at the halfway point between movement onset and cessation" [PRIMARY]. HI trajectories had reversals, abrupt velocity changes, frequent fixation corrections; polynomial order +1 per 20 dB hearing loss.
- Example trajectories (single NH listener, Fig. 2): 60-deg jump (-15 -> +45): onset ~0.2 s, peak ~120 deg/s, fixated at 36 deg by ~0.8 s => 9-deg undershoot. 30-deg jump (+15 -> +45): onset within 0.2 s, peak ~90 deg/s, overshot ~5 deg, then fixated at 29 deg by ~1.1 s. [PRIMARY, text describing Fig. 2]
- Final fixation: "all listeners undershot both auditory targets ... and visual targets ..., and the amount of undershoot tended to increase as the loudspeaker eccentricity increased." NH: auditory and visual fixation positions the same. Magnitudes only in Fig. 3 (not readable from XML). [PRIMARY, qualitative]
- Overshoots counted with 7.5 and 3.25 deg criteria (counts only in Fig. 7; no relation to hearing loss). [PRIMARY, qualitative]
- Head pitch varied only 1.9 +- 1.0 deg during yaw turns; roll coupled to yaw (~10 deg roll toward right shoulder at far-right yaw, ~7 deg left). [PRIMARY]
- Note: no effect of eyes-open vs eyes-closed on any measure. [PRIMARY]
Use for simulator: onset latency ~0.4 s (NH, free field, speech); time-to-settle ~0.9 s; sigmoidal profile with peak velocity ~50 deg/s @30 deg, ~120 deg/s @60 deg, ~150 deg/s @105 deg; undershoot that grows with eccentricity (e.g., ~9 deg at 60-deg jump in example).

