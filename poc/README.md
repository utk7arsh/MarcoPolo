# Marco Polo POCs: how to run

These are research experiments, including rejected approaches and features outside the current demo. Their results do not establish physical-device performance or the current product scope. Start with [the roadmap](../docs/HACKATHON-ROADMAP.md) and [STATUS.md](../STATUS.md) for the implemented system.

Everything is local. Python lives in a venv in this folder. The Swift tools build with Xcode Command Line Tools on macOS 15+.

```bash
cd poc   # from the repository root
PY=.venv/bin/python

# 0. Emulator fidelity tests (19 tests)
$PY -m pytest -q validation/

# 1. Apple's real spatial-audio engine: extract HRIRs, then validate head-rotation behaviour
(cd emulators/apple_audio && swiftc -O extract_hrir.swift -o extract_hrir && swiftc -O dynamic_render.swift -o dynamic_render)
emulators/apple_audio/extract_hrir hrtfhq data/apple_hrir 1.0
$PY validation/v_apple_dynamic_headtracking.py && $PY validation/v_apple_dynamic_headtracking.py --lag

# 2. Simulated listener: build the feature cache, calibrate, validate
$PY emulators/listener/cache.py && $PY validation/v_listener_model.py

# 3. POCs (results are written to reports/*.json)
$PY pocs/poc1_mapping/run.py          # 3D mapping accuracy           (~30 s)
$PY pocs/poc2_moved/run.py            # moved-item logic, 6 scenarios (~5 min)
$PY pocs/poc3_walk/run.py             # distance/direction while walking
$PY pocs/poc4_headtracking/run.py     # head-tracking pipelines
$PY pocs/poc5_guidance/sim.py         # guidance strategies           (~30 s)
$PY pocs/poc5_guidance/sensitivity.py # latency / tracking error / pace / listener ability (~1.5 min)
$PY pocs/poc7_reach_fov/run.py        # chest-camera geometry
$PY pocs/poc9_layout/run.py           # "what's on the table" by ear
$PY pocs/poc11_wearables/run.py && $PY pocs/poc11_wearables/run.py --resight   # chest vs glasses vs cap capture
$PY -I pocs/poc11_wearables/fps_sweep.py   # put-downs caught at 0.5 / 1 / 2 / 3 fps sent to the server
$PY pocs/poc12_routing/run.py         # breadcrumb routing around furniture + floor-hazard geometry
$PY pocs/poc13_voice_labels/run.py    # spatial voice labels on identical jars (row matching vs anchors)
$PY pocs/poc15_floor_hazards/run.py   # trip-hazard alerts from the chest LiDAR while walking (~1.5 min)
$PY pocs/poc16_reach_catch/run.py     # can "that's cinnamon" arrive before contact / before lifting?
$PY -I pocs/poc17_vision_real/fetch.py && pocs/poc17_vision_real/vision data/tmp/vision17 data/downloads/commons/*/image.jpg   # Apple Vision OCR + hand pose on real photos
pocs/poc18_voice_label_audio/render_label <memo.caf> <out.caf> 30 -35 0.5   # iMessage-style Opus memo -> spatial label
$PY -I pocs/poc14_drop_audio/fetch.py && pocs/poc14_drop_audio/classify data/tmp/drop_cls.json <clips...> && $PY pocs/poc14_drop_audio/analyze.py
# POC 22: find a REGISTERED item (ORBIT frames; run from data/models, where the YOLOE weights live)
(cd data/models && ../../$PY -I ../../pocs/poc22_registered_find/orbit_fetch.py)            # HTTP range reads from ORBIT's zip
(cd data/models && ../../$PY -I ../../pocs/poc22_registered_find/bench.py owlv2_image yoloe26x_vp [--lookalikes])   # any method keys in bench.py
(cd data/models && ../../$PY -I ../../pocs/poc22_registered_find/registration_study.py)     # which photo, how many, with the name
(cd data/models && ../../$PY -I ../../pocs/poc22_registered_find/query_modes.py)            # which region of the photo becomes the query
(cd data/models && ../../$PY -I ../../pocs/poc22_registered_find/server_latency.py)         # ms per phone frame, registration encoded once
$PY -I tools/plot_poc22.py    # -> reports/figures/poc22_find_registered_items.png, poc22_one_shot_photo_quality.png
# Implementation checks (POC 23-26)
(cd data/tmp && ../../$PY -I ../../pocs/poc23_box_to_3d/run.py)                   # stale pose, rotation/scale, EXIF pitfalls
(cd data/tmp && ../../$PY -I ../../pocs/poc24_touch_3d/run.py)                    # 3D touch vs 2D overlap, hidden fingertips
(cd data/models && ../../$PY -I ../../pocs/poc25_presence_and_gate/run.py)        # "is my item in this frame?" + retake gate
(cd data/models && ../../$PY -I ../../pocs/poc25_presence_and_gate/fixes.py)      # presence score fixes; verifier.py adds DINOv2
(cd data/models && ../../$PY -I ../../pocs/poc26_server/check.py)                 # server prototype, in-process (no socket)
$PY -I tools/md2docx.py REQUIREMENTS.md REQUIREMENTS.docx                         # Google-Docs-ready requirements
# Concept docs: FEATURES.md (feature specs + evidence), EVERYDAY.md (wearable design), POSITIONING.md (positioning, demo), REPORT.md (feasibility)
# POC 6 (Vision feature prints on Objectron videos): see pocs/poc6_recognition/*.swift + analyze.py
# POC 8 (offline fuzzy query): pocs/poc8_query/nl_query.swift (fm_query.swift needs Apple Intelligence on)
# POC 10 (drop sound classes): pocs/poc10_drop/labels.swift

# 4. Listenable binaural demos through Apple's HRTF (headphones; turn macOS "Spatialize Stereo" off)
$PY tools/render_demo.py   # -> reports/audio/*.wav
```

The external data (all public, read-only downloads) is in `data/downloads/`, one folder per file:

- ARI human HRTFs and MIT KEMAR from sofacoustics.org
- 8 Google Objectron bottle videos
- ARKitScenes LiDAR samples, which the research agent placed under `research/datasets_probe/`

**Cleanup, if wanted later (nothing has been deleted):**

- `data/tmp/`: intermediate render and feature files
- `research/.scratch/`: agent scratch scripts
- `emulators/**` and `pocs/**` compiled Swift binaries, which can be rebuilt
- `.venv/`
