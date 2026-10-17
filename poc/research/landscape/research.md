# Academic + industry-research prior-art sweep (2016-2026) for Marco Polo

Compiled 2026-10-16 (read-only). Slice: academic and industry RESEARCH (CHI, ASSETS, UIST, IUI, IMWUT, TACCESS, CV workshops, arXiv).
Already covered in ../pain_points_and_landscape.md and not re-described here: MemPal, GO-Finder, NaviSense, AIGuide, ORBIT, QaEgo4D.

Tags: [VERIFIED] = abstract and/or paper text read by me (via OpenAlex abstract API, Europe PMC full text, or arXiv HTML);
[SNIPPET] = only a title/abstract fragment or a citation seen secondhand; [INFERENCE] = my reasoning.
Search tooling: DuckDuckGo returned a bot challenge (not attempted). Used OpenAlex API (primary), arXiv HTML, Europe PMC,
Semantic Scholar (rate-limited 429 after a few calls). Raw outputs: research_raw/ (s*.txt = searches, a*.txt = full abstracts,
fulltext/ = paper text). Helper: tools/litsearch.py (GET-only).

Feature codes: F1 spatial-audio guidance to object | F2 LiDAR/ARKit 3D map/anchors | F3 on-demand search |
F4 passive persistent memory of put-down locations | F5 proactive alerts (moved/dropped/left without) | F6 hands-free wearable |
F7 tell identical items apart at touch (hand tracking) | F8 labels from others / voice labels | F9 register personal items (teachable) |
F10 floor-hazard / fall prevention | F11 BLV / older adults.

---

## Notes by paper (raw, in order found)

### CARA: Augmented reality powers a cognitive assistant for the blind (Liu, Stiles, Meister; eLife 2018; Caltech)
https://doi.org/10.7554/eLife.37841 [VERIFIED full text via Europe PMC PMC6257813; research_raw/fulltext/cara_elife2018.txt]
- HoloLens (head-worn; its own stereo speakers; head pose is tracked). "endows objects in the environment with voices".
- Labeling: "this was accomplished by a combination of the HoloLens and the experimenter. The HoloLens scans the physical space
  and generates a 3D mesh ... the experimenter can perform manipulations such as placing and labeling virtual objects ...
  these virtual labels are tied to the physical objects in real space." Demo add-ons: YOLO detection, Vuforia sign recognition
  where the installed virtual object "persists in the space even when the sign is no longer visible".
- Modes: Scan (objects call names left to right), Spotlight (object in front speaks as you turn your head), Target (one object
  "calls repeatedly at the press of a clicker"). Spatialized hiss = collision warning. Virtual guide calls "follow me".
- 7 blind subjects, no training. Localization accuracy "3-12 degrees". Spatial-memory recall task: 1/28 errors.
  Finding a real chair with usual aid took "eight times longer and covered 13 times the distance" vs CARA.
  Multi-story building navigation on first attempt.
- Features: F1 (yes, object-originating voice, head-tracked), F2 (HoloLens mesh = same role as LiDAR), F6 (head-mounted),
  F8 (sighted experimenter labels), F11. NOT F4 (no passive memory; "spatial memory" = the user's mental map), no F5/F7.
- Significance: the "objects call out from their location" (Polo) metaphor is 8 years old in a high-profile venue.

### Making Objects Speak: Spatial Audio Guidance for Object Grasping by BVI Users (Qin, Iwasaki, Li, Iwata; IEEE/SICE SII 2026; Waseda)
https://doi.org/10.1109/SII64115.2026.11404455 [VERIFIED abstract via OpenAlex]
- "localize and reach objects using spatialized audio cues, rendered as if the objects themselves emit sound. By integrating voice
  command recognition, RGB-D-based 3D localization, and head-tracked spatial audio via Apple AirPods Pro".
- Blindfolded sighted participants, tabletop localization-to-contact; spatial audio vs speech-only: similar success, SA
  "significantly reduced task completion time and subjective workload" and higher usability.
- Features: F1 (exactly: AirPods Pro head-tracked, object-originating), F3, F2-ish (RGB-D). Not F4/F5/F7. Not tested with BLV users.

### StereoPilot: wearable target location system for BVI using spatial audio rendering (Hu, Song, Wei, Zeng; IEEE TNSRE 2022; Southeast Univ.)
https://doi.org/10.1109/TNSRE.2022.3182661 [VERIFIED abstract]
- Head-mounted RGB-D camera -> 3D sound cues. 3 BVI + 4 sighted. SAR vs speech: information transfer rate x3, positioning error -40%;
  desktop grasping completion time halved vs voice instructions.
- Features: F1, F6 (head-mounted), F3-ish, F11. No memory.

### Touvigation: Embodied Adaptive Object Acquisition for BLV Users in Unfamiliar Indoor Environments (Wang et al.; arXiv 2609.21828, Sep 2026)
https://arxiv.org/abs/2609.21828 [VERIFIED abstract + arXiv HTML read]
- Hardware is nearly identical to Marco Polo: "chest-mounted, LiDAR-equipped iPhone" in a chest harness, ARKit VIO + LiDAR depth,
  Apple Vision VNDetectHumanHandPoseRequest (index fingertip) for reach guidance from ~0.75 m; confirms acquisition when palm is
  within 10 cm of the target box. YOLO + cloud LLM verification ("multi-view voting").
- Guidance is VOICE only (clock bearings, personalized step counts); no spatial audio found in text. "Persistent" = target stored as
  a 3D box in the SLAM world for the current search, so the user can leave the camera FOV. No cross-session memory found.
  Tactile verification = user confirms by feel from described shape/height; paper notes similar-feeling objects can be confused.
- 12 blind participants, 144 trials: success 100% (48/48) vs MLLM assistant Doubao 58% vs unassisted 85%; mean time 77.5 s vs
  170.1 s vs 105.9 s; NASA-TLX 24.2 vs 50.1 vs 43.5. Limitations: needs LiDAR, initial room scan, stable tracking; layout changes /
  moving objects make target info stale; cloud dependence.
- Features: F2, F3, F6 (chest), F11, hand tracking for reaching (not identification). Not F1, F4, F5, F7, F8.
- Significance: the chest-vest LiDAR iPhone + hand tracking form factor is already published (Sept 2026).

### (Touvigation verification) arXiv HTML grepped directly: "chest-mounted, LiDAR-equipped iPhone", "phone mounted on a chest harness",
"iPhone 15 Pro Max", "VNDetectHumanHandPoseRequest", 48/48 vs 28/48 vs 41/48, 0.75 m, 10 cm; zero hits for AirPods/spatialized/earphone/
bone conduction/"across sessions". [VERIFIED; research_raw/fulltext/touvigation_2609.21828.txt]. Affiliations (OpenAlex): HKUST (Guangzhou), NYU.

### TouchScribe: Augmenting Non-Visual Hand-Object Interactions with Automated Live Visual Descriptions (Chang, Natalie, Xu, Yap, Luo, Potluri, Guo; CHI 2026; U. Michigan)
https://doi.org/10.1145/3772318.3791308 ; arXiv 2602.07802 [VERIFIED abstract + arXiv HTML; research_raw/fulltext/touchscribe_2602.07802.txt]
- "neck mount with an attached iPhone 13 Pro" (wide lens). MediaPipe hand landmarks -> custom gesture classifier (grab to inspect,
  hold side-by-side to compare, point to explore color, swipe to read text); Hands23 for hand-object contact; keyframe on stable
  hold/touch state triggers Moondream (brief) and GPT-4o (detailed, text reading, comparison).
- Tasks with 8 BLV participants (lab): a graphic mug, "distinguishing two Trader Joe's spice jars", categorizing four hand sanitizer
  sprays. Example output: "Similarities: both are Trader Joe's seasonings in clear glass bottles. Differences: the Chile Lime bottle ...".
- Results: gesture model F1 = 0.77 live; latency 0.56 s to 14 s by description type; description accuracy 67.83% to 93.27%.
  Limitations: wide-FoV distortion, information overload during rapid gesture changes.
- No object memory (short crop history only for flip detection). No registered/personal items or family labels.
- Features: F7 (touch/hold-triggered identification incl. spice jars), F6 (neck mount), F11. It reads VISIBLE differences (labels,
  colours); it cannot separate truly identical, unlabeled containers.

### LocatAR: An AR Object Search Assistance System for a Shared Space (Oshimi, Perusquia-Hernandez, Isoyama, Uchiyama, Kiyokawa; Augmented Humans 2023; NAIST)
https://doi.org/10.1145/3582700.3582712 [VERIFIED abstract via S2/OpenAlex; full text 403 at ACM, hardware not verified]
- "pre-registration-free, and 3D location-based item management system ... automatic registration is performed by image-based item
  movement recognition from the user's grasping and placing motions. The registered item movement data comprises the item category,
  and the start and end locations ... storing item movement data without images ... refuse to share the items with other users."
  Search by item list or "where the user last saw the item"; "search and guidance functions are effective" (time + UX).
  Discussion: "treating item location as an identifier of the moved item".
- Features: F4 (passive put-down logging from grasp/place), F2 (3D AR), shared space (multi-user, cf. F8/"someone moved it"),
  guidance (AR, modality not verified). Sighted users (no BLV framing in abstract). No F1, F11.

### LiSee: headphone providing all-day assistance for BLV users to reach surrounding objects (Chen et al.; IMWUT 6(3) 2022)
https://doi.org/10.1145/3550282 [VERIFIED abstract]
- Wearable "disguised as a neckband headphone"; real-time image processing; "personalized guidance scheme"; lab + participants' homes;
  "can meet the daily needs of most participants to reach surrounding objects". Guidance modality not verified (ACM 403).
- Features: F6, F3/reach guidance, F11.

### Hand-guidance papers cited by Touvigation [VERIFIED abstracts]
- Take My Hand / FingerRover (Rahman, Azim, Heo; CHI 2023) https://doi.org/10.1145/3544548.3581415 : on-finger robot carries finger to target.
- Seeing with the Hands (Teng, Kim, Liu, Lopes; CHI 2025) https://doi.org/10.1145/3706598.3713419 : wrist camera -> back-of-hand
  electrotactile display; reach & hover; bottles, soldering irons.
- Understanding the Feasibility of Auditory Hand-Steering Guidance for BLV (Abe, Lin, Hara, Sakamoto; CHI 2026)
  https://doi.org/10.1145/3772318.3790782 : 12 BLV; VERBAL 24.6% error vs Follow-Your-Finger sonification 4.17% (1.39% for those who
  preferred it). Supports non-verbal sonified hand guidance over speech.
- Spatial alignment of audio-haptic directional feedback (IJHCS 2026) https://doi.org/10.1016/j.ijhcs.2026.103921 : wrist-worn reaching;
  aligned audio+vibration faster/more direct than axis-split.

### Find My Things (Morrison, Grayson, Marques, Massiceti, Longden, Wen, Cutrell; ASSETS 2023; Microsoft Research)
https://doi.org/10.1145/3597638.3608395 [VERIFIED abstract] ; CHI EA 2024 companion (Wen et al.) [SNIPPET, via Touvigation refs]
- "end-to-end application that can be taught by people who are blind or low vision to find their personal things"; design
  considerations for the teaching loop. Features: F9, F3, phone guidance (audio/haptic per MSR story in landscape notes), F11.

### Other LiDAR/phone items [VERIFIED abstracts]
- Kim, Sahas, Bessho, ICCE 2025 https://doi.org/10.1109/ICCE63647.2025.10929822 : multimodal LLM + iPhone LiDAR; audio/vibrotactile for
  objects in front of camera; 1 blind expert. F2, F3.
- Blindaid (Int. J. Environmental Sciences 11(3s) 2025, special issue; low-quality venue) https://theaspd.com/index.php/ijes/article/view/323 :
  "recognizes the object the user is using and recalls its most recent location", SLAM + IoT, voice in/out, runs in background.
  Conceptually F4 + F3 for blind users; no evaluation details seen. [VERIFIED abstract page]
- Hong & Kacorri, ASSETS 2024 https://doi.org/10.1145/3663548.3675635 : 12 BLV; participants "identified only half of the errors" of an
  object recognizer. Relevant risk for any recognizer-based labeling.

### Egocentric object memory (CV) [VERIFIED abstracts]
- Never Look Back / Ledger (Chaudhari, Paul, Saria, Chellappa, Bharadhwaj; arXiv 2610.10538, Oct 2026; JHU)
  https://arxiv.org/abs/2610.10538 : "persistent 3D object memory that combines object locations, their histories, and contextual
  descriptions ... retains objects after they leave the view, including those the person never touches ... records a move only after
  repeated evidence". HD-EPIC accuracy 29.7% -> 42.6%; UCS-Bench 33.8% -> 38.5%; Ego4D objects localized with 0.99 m median error.
  Offline video; no user, no guidance. F4 + "moved" history (F5 precursor).
- Instance Tracking in 3D Scenes from Egocentric Videos, IT3DEgo (Zhao, Ma, Kong, Fowlkes; CVPR 2024) https://doi.org/10.1109/CVPR52733.2024.02071 :
  RGB-D + pose; enrollment "on-the-fly based on the human wearer's interactions" or "multi-view pre-enrollment"; argues 3D world coords
  make it easier. F4 + F9 (enrollment).
- Episodic Memory Question Answering (Datta et al.; CVPR 2022; Georgia Tech/Meta) https://doi.org/10.1109/CVPR52688.2022.01853 :
  glasses "passively capture"; "where did you last see my keys?"; answer localized on allocentric top-down semantic map. F4 (+F2-ish).
- R4DSG (arXiv 2608.11017, 2026): object-centric memory for "where an item was moved, when it last changed state"; +6.7 pts on
  EgoLifeQA object subset. F4/F5-moved.
- Vinci2 / EgoServe (arXiv 2607.11523, 2026): proactive egocentric assistance benchmark (3,000+ instances; "immediate safety alerts to
  long-term habit coaching"). F5 (generic).
- ProMemAssist (UIST 2025) https://doi.org/10.1145/3746059.3747770 : smart glasses model working memory to time proactive assistance. F5-generic.
- "Remind Me To Check The Stove Before I Leave The House" (arXiv 2605.23085, 2026): NL-authored smart-home reminders (N=40, N=10).
  Leaving-home trigger but sensor/smart-home based, not object memory.

### More guidance-to-object papers (spatial audio / sonification) [VERIFIED abstracts unless noted]
- From Vision to Sound: Enhanced Object Localization for VI and Blind (Kuzdeuov et al.; ICCAR 2025; Nazarbayev U./Yale)
  https://doi.org/10.1109/ICCAR64901.2025.11073053 : "wearable visual assistance system ... locating personal items ... object detection with
  spatial sound feedback", local edge device; 44 participants (visual status not stated in abstract): localization time -37%, success
  rate x2.2. README (github.com/IS2AI/visual_assistant): RealSense D435, YOLOv7 nano (COCO + faces), Norfair 2D tracking; mounting and
  audio rendering not described. F1, F3, F6, F11. No memory.
- Acoustic touch (Jin et al.; PsyArXiv 2022; U. Sydney/UTS) https://doi.org/10.31234/osf.io/qse5h : Nreal AR glasses; recognizes and
  localizes objects, "renders objects as sound within a limited field-of-view" (foveated audio) for close reaching; compared with verbal
  clock-face and Bluetooth speakers at the objects; blind + blindfolded participants. F1, F6, F11.
- Spotlights and Soundscapes (May, Tomlinson, Ma, Roberts, Walker; TACCESS 2020; Georgia Tech) https://doi.org/10.1145/3378576 :
  dense mixed-reality spatial-audio landmark environments for cognitive-map formation; VR prototyping then real building. F1 (landmarks), F11.
- Guarese et al., OzCHI 2022 https://doi.org/10.1145/3572921.3572929 and thesis 2024 https://doi.org/10.5753/svr_estendido.2024.243612 :
  7 sonification methods for 2D micro-guidance (pantry items, appliances); spatiality helps; height-to-pitch best for vertical (N=19).
- Trant et al., Sci Rep 2025 https://doi.org/10.1038/s41598-025-21720-0 : 41 participants; vibrotactile bracelet 90.6% localization
  accuracy; auditory cues faster for grasping, but 15 did better with tactile. Supports a haptic fallback.
- Privitera, Fontana, Geronazzo, CHItaly 2023 https://doi.org/10.1145/3605390.3605422 : iPad ARKit + AirPods Pro head tracking for
  perceived virtual-source position (eye- and ground-level); users "prefer more stable tracking solutions despite accuracy".
- VizWiz::LocateIt (Bigham et al.; CVPRW 2010, pre-2016 baseline) https://doi.org/10.1109/CVPRW.2010.5543821 : photo -> remote workers
  outline object -> CV guides the user from the phone. Crowd label + guidance (F3, F8). [VERIFIED abstract]

### More LiDAR / phone object finding
- NAAD (Xie & Seals; ICCE 2023; Auburn) https://doi.org/10.1109/ICCE56470.2023.10043516 : iPhone LiDAR app for obstacle avoidance,
  item query and indoor navigation; "guide users to find user-specified lost items in the same or different spaces". Whether items are
  remembered passively is not stated. F2, F3, (F4?), F11. [VERIFIED abstract only]
- Hirai et al., J. Asian Architecture & Building Eng. 2026 https://doi.org/10.1080/13467581.2026.2709913 : 8 VI participants searching
  objects in 3D with current apps; step-by-step narrowing ("ATARI") combining app feedback with touch and prior experience. Context.

### More passive-memory / "someone moved it" / proactive
- CamFi (Yan et al.; CHI EA 2022; Zhejiang U.) https://doi.org/10.1145/3491101.3519780 : fixed camera + object detection + face recognition
  + phone app; helps "whether the user forgets where the object is or because someone else has moved the object"; n=12, multi-person
  public settings. F4 + "moved by others" (answered on query, not proactive). Sighted.
- Object retrieval using contact history from a thermal camera (Tanaka, Kishino, Shimonishi; ICCE 2025; U. Osaka)
  https://doi.org/10.1109/ICCE63647.2025.10930068 : RGB detection + thermal contact detection -> history "limited to objects touched by a
  person"; retrieval time -47.3%, workload -32.7%. F4 (touch-gated logging). Sighted.
- NeighboAR (Slavuljica et al.; PACM HCI 2024; St. Gallen) https://doi.org/10.1145/3655599 : gaze-enabled AR stores object proximity graph
  + gaze dwell; N=17; retrieval time -33%, errors -71%. F4-ish (AR, sighted).
- AcousTrack (Kim, Kim, Han; MobiSys 2024 poster) https://doi.org/10.1145/3643832.3661411 : smartwatch microphone hears objects contacting
  surfaces -> object type 92.2%, location 98.3% (3 objects x 3 locations). Only research found on sound-based put-down/drop logging.
- Support System for Preventing Forgetfulness Before Going Out Using Mixed Reality (Kume & Lopez; PERSUASIVE 2026 satellite, CCIS)
  https://doi.org/10.1007/978-3-032-27235-5_52 : leaving-home reminder in MR. [SNIPPET: title/venue only; Springer abstract behind a
  login redirect, not followed; Crossref has no abstract]
- MemoryAids (ICASSP 2026; Samsung Research America authors) https://doi.org/10.1109/ICASSP55912.2026.11462192 : proactive voice memory
  for conversations (not objects).
- Blindaid (2025) noted above; LocatAR, Ledger, IT3DEgo, EMQA, R4DSG, Vinci2, ProMemAssist noted above.

### Identical items / touch-triggered identification (F7)
- TouchScribe (CHI 2026) noted above: the direct F7 overlap (spice jars, side-by-side compare, hold-triggered).
- LifeInsight (Mathis & Schoening; CHI 2025; U. St. Gallen) https://doi.org/10.1145/3706598.3713486 : wearable camera + mic + single-click
  goal-oriented visual queries; 10 BLV diary (GoPro, one week) + 13 BLV across six scenarios; "distinguishing between jars or identifying
  the status of a candle". F3, F6, F11, F7 (on demand, not touch-triggered). [VERIFIED abstract; closed access]
- Echo (Liu & Zhao; AHFE 2026; China Academy of Art) https://doi.org/10.54941/ahfe1007292 : "semantic registration and real-time object
  finding"; "AI visual recognition identifies distinct objects ... RFID tags enable rapid identification of visually similar items such as
  documents or medicine bottles"; wristband vibrotactile; 20 VI participants, improved efficiency and success. F3, F9, F7 (by tags), F11.
- ReCog (Ahmetovic et al.; CHI 2020; IBM Research Tokyo/CMU/Milan) https://doi.org/10.1145/3313831.3376143 : blind users train recognizer
  on own photos "to differentiate personal objects, which cannot be recognized with pre-trained recognizers and may lack distinguishing
  tactile features"; verbal + sonification aiming. F9, F7-ish.
- Kacorri et al., CHI 2017 (CMU/IBM) https://doi.org/10.1145/3025453.3025899 : personal object recognizers trained by blind users, "accuracies
  over 90% for some participants". F9.
- Lee & Kacorri, Hands Holding Clues, CHI 2019 https://doi.org/10.1145/3290605.3300566 ; Lee, Shrivastava, Kacorri, Hand-Priming, WACV 2020
  https://doi.org/10.1109/WACV45572.2020.9093353 and TPAMI 2021 https://doi.org/10.1109/TPAMI.2021.3123303 : blind users put a hand on or near
  the object of interest; hand segmentation primes localization/recognition. The research basis for "the hand says which object". F7-ish, F9.
- Lee, Hong, ..., Kacorri, Revisiting Blind Photography, ASSETS 2019 https://doi.org/10.1145/3308561.3353799 : audio-haptic aiming feedback
  from object center estimated by proximity to hand; N=9; only 2%/8% photos missed the object.
- Hong & Kacorri, ASSETS 2024 (noted above): BLV users identified only half of recognizer errors.
- VizLens (Guo et al.; UIST 2016; W4A 2017 summary https://doi.org/10.1145/3058555.3058586 ; ASSETS 2023 deployment
  https://doi.org/10.1145/3597638.3614493 , 665 users) : crowd labels an appliance panel once, then CV tracks the finger and reads the button
  under it. Touch-time identification for interfaces (not objects) + crowd labels (F7-ish, F8).
- HandSight (Stearns/Findlater/Froehlich; UMD thesis 2018 https://doi.org/10.13016/wfbj-ulxc ; clothing texture with finger camera 2023
  https://doi.org/10.54364/aaiml.2023.11103 ): finger-mounted camera for touch-based access to nearby visual info. F7-ish.
- Li, Dorst, Cederberg, Carrington, Non-Visual Cooking, ASSETS 2021 https://doi.org/10.1145/3441852.3471215 : 122 YouTube videos + 12
  interviews; challenges incl. tracking task status; suggests "zero-touch interactions for cooking". Context for kitchen use cases.

### Labels from others / voice labels anchored to objects (F8)
- CARA (experimenter places labels on HoloLens mesh) noted above.
- Feasibility of Interactive 3D Map for Remote Sighted Assistance (Xie, Yu, Lee, Lyu, Billah, Carroll; arXiv 2202.01365, 2022; Penn State)
  https://arxiv.org/abs/2202.01365 : agents use interactive 3D maps with localization; 13 agents; faster assistance, lower workload.
  Related: Opportunities for Human-AI Collaboration in RSA (IUI 2022) https://doi.org/10.1145/3490099.3511113 ; Helping Helpers: AR maps
  for RSA volunteers (DIS 2022) [SNIPPET, title via citation list]. All synchronous.
- TacNote (Lee, Hung, Ting, Chi, Chen; UIST 2023; NTU) https://doi.org/10.1145/3586183.3606784 : BVI users make 3D-pen tactile labels, attach
  to objects, capture/organize with a camera app; finger-pointing + audio feedback; 10 BVI; "alleviated the memory burden". F8 (self).
- CamIO audio labeling (Coughlan et al.; 2020; Smith-Kettlewell) https://pubmed.ncbi.nlm.nih.gov/32802916 : point a stylus at a hotspot on
  a 3D object and record "a personalized audio label"; co-design with 6 blind participants. F8 (voice labels on object parts).
- Nothing found on ASYNCHRONOUS labels from family/photos anchored to positions in a persistent room map.

### Floor hazards / falls (F10)
- RASSAR (Su et al.; CHI 2024; UW) noted above: iPhone LiDAR + real-time CV flags "unsafe loose rugs", inaccessible table height; 18 formative,
  10 homes tech eval, 6-person user study. F2, F10 (on-demand scan, not continuous wearable).
- Stahl, Structured light detection and delineation of tripping hazards for people with impaired vision (Northeastern PhD 2022)
  https://doi.org/10.17760/D20474748 : wearable ETA detecting ground-plane hazards (curbs, low-contrast descending stairs); AR improved walking
  speed; "hands free, does not require eye or head-ware". F10, F6, F11.
- ALVU (Katzschmann, Araki, Rus; TNSRE 2018; MIT) https://doi.org/10.1109/TNSRE.2018.2800665 : waist belt of ToF sensors + haptic strap;
  low- and high-hanging obstacles, staircases; 12 blind users, 162 trials. F6, F10-ish.
- Fall Prevention Shoes using camera + line-laser (Lin, Yang, Shih; J. Healthcare Eng. 2017) https://doi.org/10.1155/2017/8264071 : indoor
  obstacle alarms for elderly, danger levels. F10, F11 (older adults).
- Joseph, Kian, Begg, Sensors 2023 review of wearable obstacle detection/footwear https://doi.org/10.3390/s23052802 .
- Song et al., Discover AI 2026 systematic review https://doi.org/10.1007/s44163-026-01870-4 : of >10,000 records, only 9 AI fall-risk models
  used environmental factors (3 vision/robotics); AUC 0.67-0.76; "Environmental factors remain underemphasized".
- Rusch et al., 2026, LiDAR for occupational-therapy home assessment https://doi.org/10.5130/324y0w08 : promising, protocols needed.

### Context / needs
- Gamage et al., ASSETS 2023 https://doi.org/10.1145/3597638.3608955 : 646 studies vs 24 BLV interviews; weak correlation between what
  researchers build and what BLV people rank; participants "prefer conversational agent interface and head-mounted devices".
- Chang et al., ASSETS 2025 (ChatGPT live video with 8 BVI) https://doi.org/10.1145/3663547.3746319 : good for static scenes, poor live
  descriptions, inaccurate spatial/distance info, sycophancy.

---

## Ranked list: closest to Marco Polo (already-known MemPal, GO-Finder, NaviSense, AIGuide, ORBIT, QaEgo4D excluded)

1. CARA, eLife 2018. F1 F2 F6 F8 F11 (+collision hiss). [VERIFIED full text]
2. Touvigation, arXiv 2609.21828 (Sep 2026). F2 F3 F6 F11 + hand-pose reach guidance. [VERIFIED]
3. Making Objects Speak, IEEE/SICE SII 2026. F1 F3 (F2 via RGB-D). [VERIFIED abstract]
4. TouchScribe, CHI 2026. F7 F6 F11. [VERIFIED]
5. LocatAR, Augmented Humans 2023. F4 F2 + shared space. [VERIFIED abstract]
6. From Vision to Sound, ICCAR 2025. F1 F3 F6 F11. [VERIFIED abstract]
7. StereoPilot, IEEE TNSRE 2022. F1 F6 F11. [VERIFIED abstract]
8. Never Look Back / Ledger, arXiv 2610.10538 (Oct 2026). F4 (+move history). [VERIFIED abstract]
9. CamFi, CHI EA 2022. F4 + moved-by-others. [VERIFIED abstract]
10. Thermal contact-history object retrieval, ICCE 2025. F4 (touch-gated). [VERIFIED abstract]
11. Echo, AHFE 2026. F3 F9 F7(RFID) F11. [VERIFIED abstract]
12. LifeInsight, CHI 2025. F3 F6 F11, F7 on demand. [VERIFIED abstract]
13. Find My Things, ASSETS 2023 (MSR). F9 F3 F11. [VERIFIED abstract]
14. ReCog, CHI 2020 (IBM Research Tokyo/CMU). F9 (F7-ish). [VERIFIED abstract]
15. RASSAR, CHI 2024. F10 F2. [VERIFIED abstract]
Honourable mentions: EMQA (CVPR 2022), IT3DEgo (CVPR 2024), LiSee (IMWUT 2022), Acoustic touch (2022), NAAD (ICCE 2023), Blindaid (2025),
AcousTrack (MobiSys 2024), Abe et al. CHI 2026, TacNote (UIST 2023), CamIO (2020), VizWiz::LocateIt (2010), VizLens, ALVU, Stahl 2022.

## White space and hard problems [INFERENCE from the papers above]

1. Unclaimed combination: passive, cross-session put-down memory (F4) + head-tracked spatial audio to the remembered point (F1) for BLV users
   (F11). Memory systems (LocatAR, CamFi, thermal contact, NeighboAR, Ledger, EMQA, MemPal, GO-Finder) are for sighted users or answer in
   words/visual AR. Guidance systems (CARA, Touvigation, Making Objects Speak, StereoPilot, From Vision to Sound, NaviSense) guide only to
   objects detected now or pre-labeled, within one session. Hardware and the Polo metaphor are NOT differentiators: CARA (2018) made objects
   call out; Making Objects Speak used AirPods Pro head tracking; Touvigation used a chest-harnessed LiDAR iPhone with Vision hand pose.
2. Proactive object events (F5) for BLV users: none found. Closest: CamFi ("someone else has moved the object", answered on query, fixed
   camera), PERSUASIVE 2026 MR "forgetfulness before going out" (title only), smart-home "check the stove before I leave" (2026), generic
   proactive frameworks (Vinci2, ProMemAssist). Drop detection: only AcousTrack (smartwatch hears set-down; 3 objects x 3 places).
3. F7 is partly claimed and genuinely hard. TouchScribe already does hold-triggered spice-jar comparison, but by reading visible labels
   (accuracy 67.8-93.3%, latency up to 14 s, gesture F1 0.77). Truly identical containers cannot be separated by appearance: Echo fell back
   to RFID tags for "visually similar items such as documents or medicine bottles"; ReCog/Kacorri teachable recognizers need distinguishing
   visual features; Hong & Kacorri (ASSETS 2024): blind users caught only half of recognizer errors. The remaining route is identity by
   tracking from the moment of placement (LocatAR proposes "item location as an identifier"), which no paper shows working at touch time.
4. Persistence/re-identification is the main technical risk: Ledger reaches 42.6% on HD-EPIC with 0.99 m median error and needs repeated
   evidence to log a move; Touvigation lists layout changes, moving objects, occlusion and tracking drift as limitations; IT3DEgo says 3D world
   coordinates help. A judge-proof demo should show re-localization across an app restart.
5. F8 and F10 are thin but off-core. Labels from others are synchronous or researcher-run (CARA experimenter, VizWiz::LocateIt crowd,
   3D-map RSA); self-made labels exist (TacNote, CamIO); asynchronous family photo labels anchored in a persistent room map were not found.
   Falls: RASSAR scans hazards on demand; Stahl/ALVU detect ground hazards while walking; a 2026 review found only 9 of >10,000 records using
   environmental factors in AI fall models. Open, but a different product; bolting it on may dilute the pitch.

## Search log
- DuckDuckGo helper: bot challenge (not completed). arXiv API + Semantic Scholar API: 429 after a few calls.
- OpenAlex queries: research_raw/s01-s21; full abstracts: a01-a15; citing-paper chase (MemPal, NaviSense, AIGuide, CARA, Find My Things,
  LocatAR, GO-Finder): s17_citing.txt. Full texts read: CARA (Europe PMC), TouchScribe and Touvigation (arXiv HTML).
- Not obtained: ACM full texts (403) for LocatAR, LiSee, CamFi, LifeInsight; Springer chapter for the MR forgetfulness paper (login redirect).
