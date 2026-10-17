# Prior-art sweep: hackathon projects and open-source repos

Sweep date: 2026-10-16. The sweep agent was stopped before it wrote its list; this file was finished from its
harvest (1,474 unique Devpost projects and 1,255 GitHub repos; raw files not kept here) by keyword
filtering, then reading the closest pages through the r.jina.ai reader (Devpost returns 403 to direct fetches).
Tags: [VERIFIED] = page read; [SNIPPET] = Devpost tagline from the harvest only.

## A. "Spatial audio / LiDAR finds the object" (live, on demand): crowded

- **Solaura**: iPhone Pro LiDAR, YOLOv8n plus Gemini, stereo-panned beeps (direction to pan, distance to pitch and rate), then Apple Vision hand guidance to within ~2 cm. Holds the last 3D position only while the hand covers the target; no lasting memory. [VERIFIED]
- **StepSight**: OWLv2 plus Depth Anything V2, voice panned toward the object, distance in steps; live search, no memory; Hugging Face Space. [VERIFIED]
- **Reach**: "Say 'find my keys' and Reach guides your hand to them", iPhone LiDAR, Gemini, spoken directions. [SNIPPET]
- **Proprio**: ask for an item, and a voice guides your hand. [SNIPPET]
- **Cyclops**: say what you're looking for; the phone camera finds it and walks you there. [SNIPPET]
- **AudioVision**: spatial hearing for VI users; find objects indoors, identify products. [SNIPPET]
- **InsightAI**: winner; object plus depth recognition with binaural AR audio. [SNIPPET]
- **EchoAI**: winner; "See the world through sound and LiDAR", hands-free. [SNIPPET]
- **Seekr**: VI users find misplaced objects with the phone camera and spoken guidance. [SNIPPET]
- GitHub: devmustafatavasli/Seeker (LiDAR object finding for blind users), nick8592/haptic-guide (YOLO26 plus haptic and audio), Notsk1/PythonEAD (master's thesis, object finding for VI). [SNIPPET]

## B. "AI memory finds lost items": crowded, mostly dementia and older adults, answers in words

- **Mira**: TreeHacks 2026 (inferred from the repo name), winner. Ray-Ban Meta glasses, Android relay, laptop and A100s. Builds a 3D map from a phone video walkthrough and searches it on demand; voice answers; caregiver dashboard and alerts. Continuous scene updates are listed as future work. [VERIFIED]
- **Project Memoria**: winner, plus "3.0" variants. Dementia: recalls conversations, finds lost objects, flags hazards, alerts caregivers to falls. [SNIPPET]
- **SIGHTLINE**: VTHacks 14. iPhone or Ray-Ban Meta; passively keeps a searchable visual memory; "Recall" rewinds to the moment and answers by voice. Not blind-specific; no spatial audio. [VERIFIED]
- **AURIC**: Hack the North 2026. Meta glasses plus iPhone; "remember where I put this" by voice; ESP32 radio badges with Geiger-style taps; 3D Gaussian-splat rooms (guidance is future work). Not blind-specific. [VERIFIED]
- Others [SNIPPET]:
  - Vigil: always-watching second memory for Alzheimer's, finds lost items, alerts family.
  - Senova: passively watches through a live camera, answers questions.
  - Gemini Episodic Memory (GEM): a wearable that finds lost objects for dementia.
  - FoundIT: remembers where things are.
  - Remember: Snap Spectacles memory graph, "recall where things are".
  - Palace: "AI remembers with spatial memory".
  - aerograph: "spatial memory engine".
  - Spatial Search: logs misplaced items in real time.
  - Ember: dementia; hunts lost items with a room-scanning camera.
  - EchoMemory AI.
  - Claudio (GitHub): continuous camera for dementia.
- GitHub alexbuildstech/assistivetech: webcam plus Gemini; logs object positions in SQLite relative to the frame (no SLAM); HRTF-style directional audio; a research prototype that names no target users. [VERIFIED]
- **BlindSpot**: Cal Hacks 4.0 (~2017), Best Use of Azure. Obstacle warnings plus *face* memory; no object memory or spatial audio. [VERIFIED]

## C. Not found in the harvest (keyword search plus page reads)

- Passive put-down memory that lasts across days **and** guides a blind user back to the spot with head-tracked spatial audio.
- Telling identical, unlabeled items apart at the moment of touch, by tracking which one was put where.
- Family labels from photos pinned to positions in a saved 3D room map.
- Proactive "you dropped it, it's here" or "leaving without your keys" for blind users without tags.
The harvest is keyword-based and not exhaustive. "Not found" means not found, not "does not exist".
