# ARKit + LiDAR facts for the Marco Polo emulator

Tags: MEASURED = numbers we computed from real data on disk, or numbers a paper measured. DOCUMENTED = Apple docs or WWDC. ANECDOTAL = forums or blogs.

## Numbers for the emulator

| Quantity | Emulator value | Tag / source |
|---|---|---|
| Depth map | 256x192 Float32 (`fdep`), meters | DOCUMENTED (ARDepthData docs; ARKitScenes and ScanNet++ store 256x192) |
| Depth semantics | z-depth, measured from the camera plane (not radial) | DOCUMENTED ("distance from the plane of the camera", WWDC20-10611) |
| Depth rate | 60 Hz, one map per ARFrame | DOCUMENTED (WWDC20-10611); MEASURED: ARKitScenes lowres_depth dt = 16.7 ms, 60.02 fps |
| Confidence | UInt8 (`L008`), 0 = low, 1 = med, 2 = high | DOCUMENTED |
| Confidence mix (indoor homes) | high 94%, med 4.2%, low 1.6% | MEASURED (40 frames from 2 ARKitScenes videos); Ganj 2023: about 1.6% low on average |
| Depth holes | ARKit gives no zeros (dense ML fusion). Bad pixels are flagged through confidence instead | MEASURED: lowres zero fraction = 0.0000 |
| Raw emitter | 576 points (24x24 = 9 sectors of 8x8), 26 mm-equivalent FOV | MEASURED (Luetzenburg 2021; Teppati Losè 2022) |
| Max range | 5 m. ARKit mesh debug view shows everything past 5 m as white | DOCUMENTED/MEASURED (Luetzenburg; WWDC20-10612) |
| Depth error, high confidence | bias about -1.6 to -3 cm (reads short); sd 2.3 cm at 0.5-1 m, rising to 4.7 cm at 3-4 m | MEASURED (table below) |
| Depth error at edges | RMSE 27 cm, p90 45 cm, only 62% high confidence | MEASURED |
| Small objects (smaller than about 3 cm across) | blended toward the background: +11 to +15 cm (too far), sd 20-25 cm | MEASURED (protrusion analysis) |
| RGB stream | 1920x1440 @ 60 fps (default). 4K 3840x2160 @ 30 fps (iOS 16+). Other sizes: 1920x1080, 1440x1080, 1280x720, 640x480 | DOCUMENTED (WWDC22-10126, analytics report); ScanNet++ 1920x1440 @ 60 |
| Intrinsics @1920x1440 | fx = fy ≈ 1600 px (range 1570-1630), cx ≈ 937, cy ≈ 708-713. Per-frame jitter in fx is about ±5 px (sd); cx/cy about ±0.5 px | MEASURED (ARKitScenes iPad Pro 2020; Objectron iPhone) |
| FOV (wide) | HFOV 61.9°, VFOV 48.4°, DFOV 73.7° (landscape sensor). On a portrait lanyard: horizontal 48.4°, vertical 61.9° | MEASURED |
| Depth intrinsics | fx ≈ 213, cx ≈ 125, cy ≈ 94.4 at 256x192 (the RGB values scaled by 0.1333) | MEASURED |
| Ultra-wide | Not available as ARFrame images in world tracking. Apple engineer: "World tracking automatically uses Ultra Wide camera on supported iOS devices. It is unavailable in the API." ARKitScenes ultrawide: 640x480, fx 245, HFOV 105° | DOCUMENTED (forum 831657); MEASURED |
| Pose rate | 60 Hz (each ARFrame) | DOCUMENTED; ADVIO logs pose at 60 Hz |
| VIO drift, walking | 0.2-0.5% of distance travelled (relative ATE) on iPhone Pro over 30-50 m paths; ATE RMSE 9-13 cm. Kim 2022 end-point error 0.06-0.54% (loops of 84-514 m) | MEASURED (MobileEgo 2026 vs Vicon; Kim 2022) |
| Rotation error | RPE 0.5-1.7° per sequence when walking; up to 4° when spinning. Yaw closure 0.8° per 330° pan cycle (iPhone 14 Pro Max) | MEASURED |
| Revisit error (return to a place) | 0.2-1.5 cm at a marker you revisit while it stays in view. 25-43 cm mean after "walk away and return" (14.7 m) on iPhone 11 | MEASURED (MobileEgo; HoloMeasure) |
| Anchor error after occluded 330° pan | median 3.4-7.6 cm, max 0.56 m (iPhone 14 Pro Max). Turning on depth does not help (slightly worse) | MEASURED (Park 2026 preprint) |
| Relocalization error (older ARKit) | about 16-18 cm MAE; orientation 1.7-4.9° | MEASURED (Feigl 2020, iPhone X / iOS 12) |
| Battery | about 13% in 16 min, so roughly 45-50%/h (2018-era ARKit + CV app) | MEASURED, n = 1 (Fusco & Coughlan 2020) |
| Thermal | iPhone Pro throttles after about 2 h of continuous ARKit + LiDAR recording | ANECDOTAL/MEASURED (MobileEgo 2026) |
| Background / lock | Camera is banned in the background, so the session is interrupted and tracking stops. When it resumes you need relocalization (go back near where you were) | DOCUMENTED |

### Measured ARKit LiDAR depth error vs Faro GT (ARKitScenes upsampling val 41069021 + 48018572; 40 frames; 1.85M pixel pairs; iPad Pro 2020 LiDAR; GT is the Faro scan rendered into the wide camera and nearest-sampled at the 256x192 pixel centres)

| GT depth | all-conf bias | all-conf RMSE | high-conf bias | high-conf sd | high-conf RMSE | high-conf noise floor sd (per-frame offset removed) | % high conf |
|---|---|---|---|---|---|---|---|
| 0.0-0.5 m | +0.1 cm | 5.7 cm | -0.1 | 4.8 | 4.8 | 4.7 | 98 |
| 0.5-1.0 m | -1.5 | 3.5 | -1.6 | 2.3 | 2.8 | 2.1 | 98 |
| 1.0-1.5 m | -1.8 | 4.4 | -1.8 | 2.9 | 3.4 | 2.7 | 96 |
| 1.5-2.0 m | -1.8 | 4.7 | -1.6 | 3.3 | 3.7 | 3.2 | 95 |
| 2.0-2.5 m | -2.5 | 6.5 | -2.4 | 4.2 | 4.8 | 4.0 | 93 |
| 2.5-3.0 m | -3.0 | 6.7 | -3.0 | 4.1 | 5.0 | 4.1 | 87 |
| 3.0-4.0 m | -3.6 | 7.5 | -3.1 | 4.7 | 5.6 | 4.7 | 89 |
| 4.0-5.0 m | -2.0 | 10.4 | +0.1 | 8.9 | 8.9 | 8.9 | 77 (n=2.4k only) |

By confidence (all distances): high RMSE 3.7 cm (bias -1.75); medium RMSE 14.7 cm; low RMSE 15.8 cm (bias -5.4).
Edge pixels (GT jump >10% within 3x3): RMSE 26.9 cm, p90 |e| 45 cm. Non-edge pixels: RMSE 4.0 cm.
Frames tagged with transparent/reflective objects (TRO, 4 frames): RMSE 5.7 cm vs 4.7 cm for the rest; medium-confidence share 10% vs 3%.
Per-frame median offset: mean -1.8 cm, sd 1.1 cm, range -3.9 to +0.8. Part of this is probably GT registration and time-sync error, not sensor error.
Protrusions (GT more than 15 cm in front of the local median; size counted in lowres px, 1 px ≈ 5.6 mm at 1.2 m):
- 4 px or fewer: bias +14.6 cm, sd 25.5 cm
- 5-30 px: bias +10.9 cm, sd 20 cm, and only 70% of these pixels appear in front of the background at all
- 31-300 px: +6.8 cm, and 94% are detected

Caveats (selection bias, which makes these numbers optimistic):
- ARKitScenes drops frames where LR-vs-GT RMSE is over 7 cm, or where more than 20% of pixels are off by more than 5 cm.
- The validation set was hand-filtered to remove specular and transparent aggressors.
- Only 2 videos. The device is an iPad Pro 2020, not an iPhone (Luetzenburg and Teppati Losè found the same 576-point emitter on both).
- Cross-check: ARKitScenes/PromptDA report ARKit depth L1 2.5 cm and RMSE 4.2 cm on 5.6k validation frames. ScanNet++ (iPhone 13 Pro) reports L1 ≈ 3.5 cm, RMSE ≈ 9.9 cm, AbsRel 2.4%. That is about 2x worse in RMSE because it has less filtering. Model iPhone RMSE as 1.5-2x the table above.
- Re-run: `.venv/bin/python -I scripts/arkitscenes_depth_error.py <dir1> <dir2> datasets_probe/arkitscenes_41069021_small/val_attributes.csv` and `scripts/arkitscenes_depth_extras.py <dir1> <dir2>`.

### Emulator noise model (proposal)
For confidence = 2: z_obs = z·(1 - 0.012) + N(0, σ), with σ ≈ 1.2 cm + 1.1 cm/m · z. This fits the 2.1-4.7 cm noise floor up to 4 m. Add a per-frame common offset of N(0, 1 cm).
Confidence probabilities:
- P(high) ≈ 0.98 under 1 m, falling to about 0.88 at 3-4 m and 0.77 at 4-5 m.
- Force medium or low on edges (35% medium) and on dark, specular or transparent surfaces.
- Medium/low pixels: σ ≈ 15 cm.
Edges: mix foreground and background depths within ±1-2 lowres px (flying pixels).
Objects smaller than about 6 lowres px across: shift 50-100% of the way toward the background.
Beyond 5 m: return wrong or low-confidence values; ARKit does not return NaN.
smoothedSceneDepth: temporal EMA (Apple gives no time constant; UNKNOWN). It lowers flicker but lags on fast motion.

## 1. sceneDepth / smoothedSceneDepth
- Format, resolution, rate, semantics: see the table above.
- Pipeline: "The colored RGB image from the wide-angle camera and the depth ratings from the LiDAR scanner are fused together using advanced machine learning algorithms to create a dense depth map" (WWDC20-10611). This explains why there are no holes and why edges get smoothed.
- sceneDepth is the LiDAR reading at the moment of the frame. smoothedSceneDepth is "averaged across several frames" (DOCUMENTED). Exact window: UNKNOWN.
- If you enable personSegmentationWithDepth, you get sceneDepth "with no additional power cost".
- What drives confidence: "surfaces that are highly reflective, or that have high light absorption" and "natural light of the physical environment" (DOCUMENTED).
- Measured: medium/low confidence clusters at depth edges (38% of edge pixels) and at longer range.
- Materials (Teppati Losè 2022): no strong effect from sunlight vs shade, or across 8 materials including black opaque metal, at 1 m.
- Ganj 2023: reflective or dark surfaces absorb or scatter, and lighting changes effective range (qualitative).
- Transparent glass: ToF reads the surface behind it, or a reflection. Apple says nothing beyond "reflective". ARKitScenes ships a Has_TRO flag (94 of 5,599 val frames).
- Thin objects: see the protrusion result. Luetzenburg: models of objects with sides over 10 cm are accurate to ±1 cm; smaller objects are poor.

## 2. Depth error vs distance
See the measured table. Literature:
- Luetzenburg: ±1 cm on objects; point density 7,225 pts/m² at 25 cm and 150 pts/m² at 2.5 m.
- Günen 2023 (iPhone 12 Pro indoor mapping): RMSE 1.41 cm with the 3D Scanner app, 3.94 cm with Clirio.
- ScanNet++ and PromptDA: as above.

## 3. Video formats, camera, intrinsics
- Default world-tracking format on LiDAR iPhones: 1920x1440 @ 60, wide (1x) camera. 4K 3840x2160 @ 30 via `recommendedVideoFormatFor4KResolution` (iPhone 11+, iOS 16; the 16:9 frame is cropped).
- Image path: the sensor reads a 3840x2880 area and bins it 2x2 to 1920x1440, about every 17 ms (WWDC22).
- An iPhone 13 Pro Max lists at least 13 formats; index 12 = 4K30 (ANECDOTAL, forum 709811).
- `configurableCaptureDeviceForPrimaryCamera` (iOS 16) gives AVFoundation exposure/ISO control. Apple warns this "may affect tracking".
- Ultra-wide: used internally by world tracking. You cannot select it or read its frames. MobileEgo 2026 confirms the "ultrawide lens is inaccessible during active ARKit sessions".
- Intrinsics: see the table.
  - The ARKitScenes iPad has fx 1600.8 ± 4.7 and cx 937.1, cy 707.9.
  - The Objectron iPhone has fx 1603 (range 1579-1630), cx 937, cy 713.
  - fx changes per frame with autofocus / focus breathing (an SO question reports ~36 px of change in 4K). Use the per-frame K.
  - iPhone 12-16 Pro specific values: UNKNOWN, not measured here. Expect a similar 26 mm-equivalent lens, so HFOV about 60-65°. Sensors differ (13 Pro and later have a larger sensor), so check on the device.
- Lanyard implication: in portrait the horizontal FOV is only 48°. Items more than 24° off the chest axis are out of view.

## 4. VIO
- Numbers: see the table.
- ADVIO (iPhone 6s, 2018): ARKit was "robust with only a few clear failure cases (95th percentile ∼10 meters)" on mall and metro paths.
- Feigl 2020 (iPhone X, iOS 12, dynamic industrial hall): scale error 5.9-7.0 cm/m when relocalizing every 60-100 m; 14.6 cm/m without relocalization over 120 m. That is about 6-15%, a worst case for older devices.
- ARWorldMap: save it with `getCurrentWorldMap` once `worldMappingStatus` is `.mapped`, and load it through `initialWorldMap`. The session then sits in `.limited(.relocalizing)` until it matches the map. It stays there "indefinitely" if the place is different.
- Interruption relocalization only works if the device returns "approximately near" its pose at the interruption. Default is "a few seconds" before reset.
- Anchors: adding an anchor "helps ARKit to optimize world-tracking accuracy in the area around that anchor". ARKit copies anchors frame to frame and may update their `transform`, so subscribe to `session(_:didUpdate:)`.
- HoloMeasure: the iPhone lost tracking in 35% of walk-away runs (each loss under 1 s). ARKit loop closure after returning was worse than ARCore.
- For Fusco & Coughlan, lanyard ≈ handheld for localization (about 1 m, with marker help).

## 5. Scene reconstruction / RoomPlan
- ARMeshClassification: none, wall, floor, ceiling, table, seat, window, door (8 values).
- Mesh shown to 5 m; edges are "not crisp".
- RoomPlan (iOS 16+):
  - 16 object categories: storage, sofa, table, chair, bed, refrigerator, oven, stove, dishwasher, washer/dryer, fireplace, sink, bathtub, toilet, stairs, TV.
  - Surfaces: wall, door(isOpen), window, opening, floor.
  - Confidence levels: low/med/high.
  - Accuracy (Apple ML Research): walls and windows 95% precision/recall, doors 90% (2D IoU).
  - Objects: AP 91%, recall 90% at 3D IoU 0.3. Chair is worst at 83/87.
  - Rooms up to 15x15 m; a 5-minute scan is designed to avoid throttling.
  - Not useful for small personal items (keys, cups). Objectron and our own detector are needed for those.

## 6. Power / thermal / background
- Measured numbers are scarce. Fusco: 100% to 87% in about 16 min. MobileEgo: throttling after about 2 h of continuous capture, helped by a heat sink. PromptDA lab: an overheating iPhone could only hold 15 Hz capture.
- Thermal states: nominal/fair/serious/critical. At serious Apple suggests 60 to 30 fps. AVCaptureDevice system pressure "shutdown" interrupts capture.
- Hours of ARKit + LiDAR on battery: UNKNOWN. Measure it. A plausible estimate is 2-3 h on a modern Pro with the screen dimmed (inference, not verified).
- Background / screen lock: "Camera usage is prohibited while in the background". The session is interrupted, so no poses or depth arrive while locked. Set `isIdleTimerDisabled` and dim the screen (`UIScreen.brightness`; the setting reverts on lock). The emulator should model screen-off as a tracking gap followed by relocalization.

## 7. Motion blur / rolling shutter
- `ARCamera.exposureDuration` is exposed (iOS 13) for rendering blur. Its typical values are UNKNOWN.
- Apple forum 833148: outdoor/indoor dim light, so "longer shutter speeds" cause motion blur. The fix is manual exposure via `configurableCaptureDeviceForPrimaryCamera`, with caution.
- ScanNet++ notes iPhone video "motion blur" as a challenge.
- Walking-speed blur in px: UNKNOWN measured values. Rough estimate: a lanyard bob of about 20°/s angular velocity (ARKitScenes handheld median 17.6°/s, p95 47°/s) times a 1/60 s exposure at fx 1600 gives about 9 px of blur (inference).
- Rolling shutter readout: UNKNOWN for ARKit mode. CineD measures iPhone 15/17 Pro video RS as "great" (low ms), but not in ARKit binned mode.
- ARKit handles it internally. Tracking degrades to `.limited(.excessiveMotion)`.

## 8. Calibration datasets
- On disk under `datasets_probe/`:
  - ARKitScenes upsampling val 41069021.zip (49 MB) and 48018572.zip (47 MB): RGB 1920x1440, lowres_depth, confidence, Faro highres_depth.
  - Raw intrinsics and trajectory for 41069021.
  - Metadata CSVs.
  - Objectron cup geometry.pbdata (1.9 MB).
- ARKitScenes: https://github.com/apple/ARKitScenes (download_data.py; assets on docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1). Upsampling subset is about 2,257 sequences. Full raw is TB-scale. Pull per-video zips only.
- ScanNet++ (iPhone 13 Pro RGB-D @ 60 fps + laser GT): https://kaldir.vc.in.tum.de/scannetpp/ (requires terms; large).
- Objectron: https://github.com/google-research-datasets/Objectron (public GCS bucket objectron; per-sequence geometry.pbdata ≈ 2 MB plus video).
- ADVIO: https://github.com/AaltoVision/ADVIO (iPhone ARKit poses @ 60 Hz + GT; per-sequence zips of a few hundred MB).
- HoloMeasure app: https://github.com/SceneIt-Source/HoloMeasure.
- Clew (blind path retracing on ARKit, closest prior art): https://github.com/occamLab/Clew.
- Exact sizes for ScanNet++/ADVIO were not verified this session (the search tool hit a rate limit). UNKNOWN.

## Unknowns to measure on the real phone
1. smoothedSceneDepth time constant.
2. iPhone Pro (target model) intrinsics and FOV.
3. Battery %/h and time-to-throttle on a chest lanyard with the screen dimmed.
4. Exposure duration indoors and outdoors, and blur at walking pace.
5. Depth on glass, mirrors and black fabric.
6. Detection hit rate for keys and phones at 1-3 m.
