# Prior-art sweep: shipped apps and commercial products (Marco Polo, LA Hacks 2026)

Swept 2026-10-15/16. Read-only browsing. Tags:
- [VERIFIED] = I opened and read the page (quotes are from the WebFetch extract of that page).
- [SNIPPET] = search-result snippet only.
- [INFERENCE] = my reasoning, not stated by a source.

Feature codes: F1 spatial-audio guidance to object; F2 LiDAR/ARKit 3D/anchors; F3 on-demand search; F4 passive cross-session memory; F5 proactive alerts; F6 hands-free wearable; F7 touch-moment disambiguation via hand tracking; F8 labels from other people / voice labels; F9 pre-registering personal items; F10 floor-hazard / fall prevention; F11 BLV / older adults.

---

## 1. Microsoft Seeing AI: World channel + Find My Things (closest shipped match to the F1+F2 core)

- World channel launched December 2020, LiDAR iPhones, iOS 14. "uses an iPhone's LiDAR sensors to gain a spatial, 3D depiction"; "the identifying voice sounding as though it is emanating from its location"; objects go into a list; selecting one "will start a navigation task" that "guides the user to the object using beeps." Reviewer: "might not be used frequently by most users." [VERIFIED] https://www.second-sense.org/2022/05/seeing-ais-world-channel/ (2022-05-16)
- Beacons on objects (Saqib Shaikh, Sight Tech Global 2020 transcript): "you can even place audio beacons in the world"; "you'll place that audio beacon on the door"; "even as you move your camera or look different directions, the beacon will remain coming from the door"; "we use the Lidar to sort of build up that world understanding". Session intro also mentions a "haptic proximity sensor to feel the outline of the room". No cross-session memory mentioned. [VERIFIED] https://sighttechglobal.com/session/seeing-ai-what-happens-when-you-combine-computer-vision-lidar-and-audio-ar/
- v5.0 (2023-01-30): "On the World Channel, when using headphones which support Spatial Audio, you no longer need to look [in the camera direction]" (i.e. head tracking, AirPods 3 / Pro named in 5.0.1 notes); "Indoor Navigation ... enables you to create routes through a building". v5.3 (2024-04-05): "Find My Things - This new feature, available via the World channel". [VERIFIED] https://apps.apple.com/au/app/seeing-ai/id999062298 and https://apps.apple.com/us/app/seeing-ai/id999062298
- Still available: US App Store v5.6.1 (2025-09-04), free, still lists "World - An Audio Augmented Reality experience ... hearing objects announced around you with Spatial Audio (requires a device with a LiDAR)" and Find My Things. Listing does not mention beacons. [VERIFIED]
- Henshaws "Seeing AI: The 2025 update" (April 2025): World "only works on ... those with a LIDAR scanner"; "If the object is to the left, you will hear the announcement on the left-hand side"; head-tracking headsets supported; you can "place an audio beacon on a particular object of interest". Find My Things: teach with "four short videos", "The faster the beeps, the closer you are to the item", "it can't help you detect other objects while doing so". [VERIFIED] https://www.henshaws.org.uk/hints-and-tips/seeing-ai-the-2025-update/
- AppleVis forum, Sept 2025 (via mail.applevis.com mirror; main site is Cloudflare-blocked): World "is there for me in the More tab" (iPhone 15 Pro, AppleVis editor); on a non-LiDAR iPhone 14 the More list shows "find my things" but no World; Seeing AI support: "the Indoor Navigation feature has been removed" due to "unavailability of a key technology". [VERIFIED] https://mail.applevis.com/forum/ios-ipados/seeing-ai-where-world-channel
- Find My Things (MSR story, 2024-10-24): teach with four short videos; few-shot model personalizes on device; "audio, visual, and vibration cues to guide the person to within arm's reach"; came from the ORBIT dataset work. [VERIFIED] https://www.microsoft.com/en-us/research/story/find-my-things/
- Android: Seeing AI on Android since Dec 2023 [SNIPPET, MS accessibility blog]; Find My Things "only available on iOS devices" [SNIPPET, YouTube demo]. World needs LiDAR so effectively iPhone/iPad Pro only [INFERENCE].
- Codes: F1, F2, F3 (fixed detector classes + taught items), F9, F11. Not F4 (beacons are live-session; no passive log), not F5, F6, F7, F8.
- Implication [INFERENCE]: object finding with head-tracked audio has prior implementations. Evaluate Marco through measured persistence, identity errors and hand guidance rather than claims of novelty.

## 2. Biped NOA (biped.ai, Switzerland)

- Shoulder-worn "handsfree vest", ~1 kg, 7 h; "Three depth and infrared cameras", 170 x 90 deg, 0.3-10 m, day and night; "3D beeps through bone-conduction headphones"; alerts to "branches, holes, and scooters", stairs, nearby people; AI scene description "with just a press of a button"; GPS. Price not listed. [VERIFIED] https://www.matapo.com/biped-noa
- Market entry in ten countries (US, UK, FR, BE, DE, CZ, AU, CH, ES, NZ) by 2024-08-06; developed with Honda Research Institute; 250+ beta testers. [VERIFIED] https://ggba.swiss/en/noa-by-biped-marks-successful-market-entry-in-europe-and-the-us/
- 2024-10-29 update: object-finding buttons: "Detect doors", "Identify crosswalks", "Spot open seats", "Recognize stairs and elevators", "read text". [VERIFIED] https://bipedai.substack.com/p/new-buttons-let-you-find-objects
- Same date, v1.4.0: "automatic detection of your hands to avoid playing sounds"; "improved spatialization of 3D sounds". [VERIFIED] https://bipedai.substack.com/p/noa-detects-your-hands-and-occlusion
- Canada distributor: "Now Available in Canada", 950 g, "Directional sound alerts via bone conduction". [VERIFIED] https://www.exobot.ca/en/noa-by-bipedai ; distributor snippet says "designed for visually impaired individuals and seniors" [SNIPPET]
- "NOA Chat feature allows users to send images and videos via WhatsApp" [SNIPPET, Double Tap; page fetch failed with SSL error]
- Codes: F1 (spatial audio, but for obstacles, not to an object), F2-equivalent (own depth cameras, not iPhone LiDAR), F3 (fixed categories), F6 (shoulder vest), F10, F11. No memory.

## 3. Lumyeye Pro (LumyEYE, France)

- App Store: "'Where are my keys?' 'Find my remote.' Lumyeye helps you locate an object"; v1.8: "analyzes the scene and guides you by voice, providing direction and distance on LiDAR-compatible iPhones"; Vision Live (about 1 photo/s) up to 10 min/day; voice memos; $16.99/month; v1.0 dated May 13 (year not shown), v4.5 Oct 1; also listed for Apple Vision. [VERIFIED] https://apps.apple.com/us/app/lumyeye-pro/id6761368652
- User guide: finding objects "helps you move towards it with spoken and audible cues", can "name detected obstacles"; "Beep beep" mode: "beeps become faster as you approach"; memos to remember "where you left your keys" (manual). Guide does not mention spatial beeps. [VERIFIED] https://www.lumyeye.com/en/notice
- Vendor comparison page claims it can "play spatial beeps through headphones" and "LiDAR distance and approach beeps on compatible iPhones". [VERIFIED page, vendor claim] https://www.lumyeye.com/en/best-apps-blind-2026
- "Lumyeye Pro is now compatible with VIVE Eagle smart glasses. Press the left-temple button, speak and hear the answer" [SNIPPET, lumyeye.com homepage]
- Launch year: 2026 [INFERENCE from App Store id 6761368652 and an Aug 2026 article calling Pro "a new chapter"; VERIFIED that article gives no date].
- Codes: F1 (claimed spatial beeps; unconfirmed), F2 (LiDAR distance), F3 (open vocabulary), F4 manual only, F6 (via VIVE Eagle, snippet), F11.

## 4. SightNiq (web app/PWA, 2026)

- "Your family can update your world, even when they aren't there." Pills example: daughter moved them and left a note; the app tells you where. "SightNiq remembers helpful notes about places you go and recalls them on return"; "Save this spot"; teach items: "Snap a photo + give it a name"; Find Mode: "combines your saved memories with the current camera view to spot the thing"; Live Mode: "Hands-free continuous narration"; Ask my family: "route the question + photo to your caregivers". [VERIFIED] https://www.sightniq.com/
- About: uses Claude; object pre-pass "prioritises hazards"; memories per account (Supabase RLS); caregivers via revocable private invite link; no spatial/directional guidance or LiDAR described; Ray-Ban Meta integration "planned". [VERIFIED] https://www.sightniq.com/about
- Pricing: Free (20 queries/day, no memory); Pro ($9/1 mo, $24/3 mo, $84/12 mo, usually gifted by family): "Persistent memory of your home, plus Find Mode", "family can read activity and write memories", Teach SightNiq, "Glasses support (Mentra/Halo) when paired". [VERIFIED] https://www.sightniq.com/pricing
- Launch date and traction not stated; footer "(c) 2026 deejayits". [VERIFIED]
- Codes: F3, F4 (persistent but built from saved notes/answers; passive capture not stated), F6 (paired glasses), F8 (caregivers write memories), F9, F11. No F1/F2.

## 5. OOrion (Lyon, France)

- "scan [your items] from different angles"; "As soon as the app identifies the object, beeps, vibrations, and distance indicators guide you precisely to it"; iOS now, Android "coming soon"; free. [VERIFIED] https://www.oorion.fr/en/the-app
- App Store: "locate anything in your surroundings based on a brief description" (v8.3.0, "no longer limited to a fixed list"); "alert you when an obstacle is in your path"; v8.4.3 current. [VERIFIED] https://apps.apple.com/us/app/oorion/id1567957213
- Review 2026-06-02: five tools (Search object, Search text, Nearby objects, Nearby text, Personal Objects); "works well with Meta AI glasses but drains their battery"; obstacle warnings "sometimes too late and also incomplete". [VERIFIED] https://www.blindios.uk/oorion-describes-whats-near-and-helps-find-items-and-text
- Meta (2026-05-18): OOrion via the Wearables Device Access Toolkit; users can "scan and save personal items" such as keys, wallets, phones. [VERIFIED] https://about.fb.com/news/2026/05/meta-ai-wearables-changing-the-game-for-disabled-people/
- Company "Créée en 2022" [SNIPPET]
- Codes: F3, F6 (Meta glasses), F9, F10 (obstacle alerts), F11. Guidance is beeps/vibration/distance, spatial audio not stated.

## 6. Apple (Magnifier Detection Mode, Point and Speak, Live Recognition, Vision Pro)

- People Detection: iOS 14.2 (2020), LiDAR, distance to people [SNIPPET, CNET/AppleVis]. Door Detection: iOS 16 (2022) [SNIPPET].
- Point and Speak (announced 2023-05-16, iOS 17): "combines input from the camera, the LiDAR Scanner, and on-device machine learning"; announces button text "as users move their finger across the keypad"; LiDAR devices only. [VERIFIED] https://www.apple.com/newsroom/2023/05/apple-previews-live-speech-personal-voice-and-more-new-accessibility-features/
- Detection Mode in iOS 26 (AbilityNet): People, Doors, Furniture; labels/speech/sounds/haptics; distance estimates; "A higher pitch sound is used if a person is detected within this distance"; feedback "becomes more frequent as you get closer"; seat occupancy; Pro models only. No direction feedback described. [VERIFIED] https://mcmw.abilitynet.org.uk/how-to-detect-people-doors-and-furniture-in-your-surroundings-using-the-magnifier-app-in-ios-26-on-your-iphone-pro-or-ipad-pro
- Live Recognition: VoiceOver rotor in iOS 18 [SNIPPET]. iOS 27 (AppleVis demo 2026-09-14): "Ask" uses Apple Intelligence to describe the scene; modes shown Scenes, People, Doors; no find-object mode, no direction/distance guidance, no memory; Action button not shown. [VERIFIED] https://mail.applevis.com/podcasts/demonstration-walk-through-new-live-recognition-features-ios-27
- May 2026 preview: "press the Action button on iPhone to quickly ask a question about what's in the camera viewfinder" [VERIFIED newsroom]; one blog says these Action button options "haven't appeared" as of 2026-09-13 [VERIFIED, single small source] https://geeksmodo.com/accessibility-action-button/
- visionOS Live Recognition: describes "scenes, people, furniture, and text"; no find mode, no spatial cue described on the support page. [VERIFIED] https://support.apple.com/guide/apple-vision-pro/get-live-descriptions-with-live-recognition-tanb4e29f7a1/visionos (Apple's May 2025 announcement said "find objects" [VERIFIED in earlier notes]).
- Developer note: ARKit object tracking now "requires either an iPhone with iOS 27 or later, or an Apple Vision Pro" [SNIPPET, Apple developer docs]. Platform capability, not a product.
- AirTag / Find My: see section 10.
- Codes: F2, F3 (descriptive Q&A), F7-adjacent (Point and Speak finger tracking, for printed text only), F10-lite (people/door distance), F11.

## 7. Google (Lookout Find, Gemini Live Guided Vision, Find Hub memory, Astra)

- Lookout Find (beta May 2024): "Select from seven categories"; help page lists Seating & Tables, Doors & Windows, Cups, Bottles & Cans, Utensils & Tableware, Vehicles, Bathroom; "direction and distance guidance ... in most phones"; Android only. [VERIFIED] https://support.google.com/accessibility/android/answer/9031274 , https://blog.google/company-news/outreach-and-initiatives/accessibility/ai-accessibility-update-gaad-2024/
- September 2026 Android Drop (2026-09-01): Find Hub memory: "Hey Google, remember in Find Hub that I put my passport in my bedroom drawer", optional photo, Gemini reads it back, no passive capture, no guidance, "Soon", Android 16+. Guided Vision in Gemini Live: "Designed for and with the blind and low-vision communities", coaches you to reframe/pan/center; uses include "finding objects on cluttered counters"; "Don't use it for navigation or obstacle detection"; "coming soon", Android 9+. [VERIFIED] https://blog.google/products-and-platforms/platforms/android/Android-Drop-September-2026/ , https://whysogeek.com/android-drop-gemini-find-hub-guided-vision-2026/
- Aira's "AI Visual Interpreter powered by Project Astra": Trusted Testers waitlist; finds items, reads, describes; no memory or spatial audio mentioned. [VERIFIED] https://aira.io/ai/
- Android XR "intelligent eyewear" (I/O 2026): audio glasses "coming later this fall"; no object memory or blind-user features mentioned. [VERIFIED] https://blog.google/products-and-platforms/platforms/android/android-xr-io-2026/
- Codes: F3, F4 (manual only), F11. No F1/F2.

## 8. Meta AI glasses + Be My Eyes + Aira

- Be My Eyes "Call a Volunteer" on Ray-Ban Meta announced at Meta Connect, Sept 2024; 2026-03-11 (CSUN): hands-free Groups (trusted family/friends) and Service Directory: "Hey Meta, Be My Eyes with [name]". [VERIFIED] https://www.bemyeyes.com/news/be-my-eyes-and-meta-launch-new-accessibility-functions/
- Meta accessibility page: "describe what I'm seeing", "Detailed responses" setting, Be My Eyes volunteers, reading text; no find-objects feature. [VERIFIED] https://www.meta.com/ai-glasses/accessibility/
- Aira on Meta glasses (2026-04-20): live video to professional human interpreters. [VERIFIED] https://aira.io/aira-now-works-with-ai-glasses-from-meta/
- Reminders: explicit "Hey Meta, remember this ..."; reminders "from what you see"; no passive memory; US English. [VERIFIED] https://www.meta.com/help/ai-glasses/544073848068065/ ("remember where I parked", Connect 2024 [SNIPPET])
- "Super Sensing": FT report (2026-07-09) of prototype glasses that "continuously record audio and take photos every few seconds" to recall "where you left your keys"; prototype, not shipping. [VERIFIED secondary] https://courionai.com/news/2026-07-09-meta-super-sensing-glasses/
- Muse personal agent (Connect 2026-09-23): "coming soon"; no object-location memory described. [VERIFIED] https://www.meta.com/blog/muse-personal-agent-ai-glasses/
- Codes: F3, F4 (manual; passive only as prototype), F6, F8 (live family video via Groups), F11.

## 9. Envision (app 2018, Glasses 2020, Ally 2024, Ally Solos 2025)

- Glasses user guide (Feb 2025): Find Object = list of "pre-trained objects" (Door, Stairs, Traffic Light, Bottle, Chair, Bench, Couch, Table, Toilet, Backpack, Coffee Cup, Laptop, Computer Keyboard, Mobile Phone, Sink, Light Switch, Dog, Cat, Sunglasses, Footwear); when detected "a sound will be played, along with the clock-notation position". Find People speaks names of taught faces. Explore = objects + people from video. [VERIFIED, local PDF extract of https://nelowvision.com/wp-content/uploads/2025/02/User-Guide-Envision-Glasses-February-2025.pdf]
- Ally Solos Glasses announced 2025-08-14: read, describe, recognize faces and items, calendars/reminders; targets BLV, older adults, cognitive disabilities; $399 launch, $699 list; shipping expected Oct 2025; no object finding, memory of locations or spatial audio mentioned. [VERIFIED] https://www.letsenvision.com/blog/ally-solos-glasses
- Ally app review (AFB, summer 2025): "remembers context, learns your preferences"; after dropping keys, Ally "was given directions to find them". [VERIFIED] https://www.afb.org/aw/summer2025/ally-ai-app-review
- Envision Companion app (family as "eyes and voice" of the glasses) [SNIPPET]. Envision support site returns 403.
- Codes: F3 (fixed 20 classes on glasses), F6, F9 (faces only), F11.

## 10. Apple AirTag + Find My

- Notify When Left Behind: separation alerts for AirTags, AirPods, iPhone/iPad, Apple-silicon Macs, Find My accessories; trusted-place exclusions. [VERIFIED] https://www.idownloadblog.com/2021/09/24/what-is-find-my-notify-when-left-behind-how-to/ (iOS 15, 2021 [SNIPPET])
- Precision Finding + VoiceOver (ahead/behind/left/right, distance, haptics, ~30-35 ft range, one tag per item) [VERIFIED in ../pain_points_and_landscape.md via AppleVis].
- Codes: F1-lite (direction cues via speech/haptics, not spatial audio), F5 (tag-based), F9-equivalent (tag per item).

## 11. Brilliant Labs Halo + Noa "Narrative" memory

- Announced 2025-07-31; $299 then $349 then $399; shipping slipped to "early August" 2026 per company; 640x480 low-power camera; Noa "analyzes the wearer's daily conversations and surroundings"; example recall of "where an object was left"; no accessibility mention. [VERIFIED] https://vrarwiki.com/wiki/Brilliant_Labs_Halo ; "Halo is in production ... first shipments scheduled for early August" [SNIPPET, X]
- Codes: F4 (closest shipped passive memory; verbal only), F6. Not BLV.

## 12. Glidance Glide

- Two-wheeled handheld AI guide; steers around obstacles incl. overhead; detects "drop-offs", stairs (guides to railing), crosswalks; "can guide you to nearby targets within its camera view, such as doors, elevators, stairs, and counters"; cannot train new objects at launch; no saved routes at launch; $1,499 preorder + $30/month; preorders closed, small-batch deliveries "this year" (2026); US, CA, UK. [VERIFIED] https://www.glidance.io/frequently-asked-questions
- Codes: F3 (fixed targets), F10, F11. Not wearable.

## 13. Ariadne Sense (iPhone, c. 2025-26)

- "continuously describes what's in front of you"; "Voice and vibration warn you about obstacles: curbs, steps, posts"; "Vibration features require an iPhone with a LiDAR sensor"; object finding example "I'm looking for the remote" and it "lets you know when the object appears in frame"; handheld ("Hold the phone in front of you"); no memory or spatial audio mentioned. [VERIFIED] https://ariadnesense.com/en/
- Codes: F2, F3, F10, F11.

## 14. Clew (Olin College / Occam Lab)

- "AR indoor navigation app ... record, share, and navigate routes"; share routes via iMessage etc.; v1.6.5 "visual anchors to support route localization"; voice notes play near a spot; last update v1.6.9 (2023-10-11); earliest visible v1.2 (2019-07-21). [VERIFIED] https://apps.apple.com/us/app/clew/id1268077870 ; "designed with finding your way back to a seat or a table in mind" [SNIPPET GitHub]
- Codes: F2, F8 (voice notes on places), F11. Tracks you, not objects.

## 15. Item-labeling products

- RNIB PENfriend 3: record audio labels; "Place the PENfriend on any label to hear the recording"; up to an hour per label; 16 GB; GBP 114. [VERIFIED] https://shop.rnib.org.uk/products/rnib-penfriend-3-audio-labeller ; PENfriend1 introduced 2007 [SNIPPET]
- WayAround (Blind InSites): NFC WayTags; "write whatever info you want onto the tag"; tap to read; no AI; v4.6.5. [VERIFIED] https://apps.apple.com/us/app/wayaround-tag-and-scan/id1294361140
- Hable SpeechLabel: NFC or QR labels with voice recording (up to 1 h), titles or text; "public" labels so family can scan and hear the same message; "Unlike AI, there's no guessing". [VERIFIED] https://www.iamhable.com/pages/speechlabel
- Talking Tins: lid records a voice message, plays back at a button press. [SNIPPET] https://www.talkingproducts.com/products/talking-tins-yellow-20-seconds
- Digit-Eyes: print your own QR labels with text/audio, scan UPCs. [SNIPPET] http://digit-eyes.com/
- Codes: F7 (identify at touch, needs a tag per item), F8 (voice labels; SpeechLabel shareable), F11.

---

## Also checked (lower overlap)

- Supersense (Mediate): Smart Scanner, Find/Explore; v1.10.30 (2024-05-13); $4.99/mo. [VERIFIED App Store] Find locates "people, seats, doors, trashcans" [SNIPPET].
- Super Lidar (Mediate): v1.0 2021-01-22, last v1.2.1 2021-05-06; obstacle pitch + haptics, people and mask detection. [VERIFIED App Store] AppleVis commenters 2024-2025 call it unmaintained. [VERIFIED mirror]
- LiDAR Sense: vibration and sound up to 8 m. [SNIPPET] White Cane - Obstacle Detector: LiDAR + TrueDepth obstacle app. [SNIPPET]
- Strap Tech Ara: chest-worn, sonar, haptics, obstacles at "head, chest, and below"; $500 preorder; "available in 16 countries". [SNIPPET] (relevant to the chest-vest form factor)
- .lumen glasses: head-worn, stereo vision + haptic "guide dog"; ~1,500 preorders (~$10M), production ramping, CES 2026. [VERIFIED] https://www.indexbox.io/blog/lumen-glasses-for-the-blind-unveiled-at-ces-2026/ ; availability/price not stated on dotlumen.com [VERIFIED]
- WeWALK Smart Cane 2: above-ground obstacle detection, voice navigation, AI assistant. [SNIPPET]
- OrCam MyEye 3 Pro: reading, face recognition, product ID, money/colors, "Just Ask" AI; reading activated by "voice command, hand gesture, or touch bar". [VERIFIED] https://www.orcam.com/en-us/orcam-myeye-3-pro
- Seleste glasses (probably the "Celeste" in the brief; Vancouver): AppleVis review 2024-04-05: camera between the eyes, photo descriptions, assistant "will also remember previous images", $100 deposit + $50/month, TestFlight beta at the time. [VERIFIED mirror] Current status not verified.
- Aira: Access AI (free AI image chat with optional human verification) [SNIPPET]; Astra trusted testers, Meta glasses: sections 7 and 8.
- Be My AI (GPT-4 image description, 2023) [SNIPPET]; no live object-finding guidance found.
- Sullivan+ (TUAT, Korea): AI mode, text, face, image description. [SNIPPET]
- Oko (AYES): pedestrian-signal app, 2024 Apple Design Award. [SNIPPET]
- Remember Where - Find Items: photo of a place + item tags (optional Gemini tagging), text search; no AR, no accessibility info. [VERIFIED] https://apps.apple.com/us/app/remember-where-find-items/id6798571264
- AnchorThis: manual "say where you put it once" memory. [VERIFIED earlier notes]

## Older-adult fall / hazard tech using cameras or LiDAR

- VirtuSense VSTAlert: room "LIDAR Sensor monitoring ... (not a camera)", "Detects intent to exit a bed or chair", "Notifies staff 31-60 seconds before a fall"; senior living, skilled nursing. [VERIFIED] https://www.virtusense.ai/solutions/senior-living
- Nobi smart lamp: ceiling lamp with "optical care sensors" + on-device AI; fall detection, automatic night lighting, stick-figure images; care homes and home. [VERIFIED] https://www.nobi.life/en/product
- Kami Vision, SafelyYou, AltumView Sentinare: camera fall detection. [SNIPPET]
- Apple Walking Steadiness (iOS 15): iPhone near the waist assesses "balance, strength, and gait", notifies when low. [SNIPPET Apple Support]
- No wearable camera/LiDAR floor-hazard product aimed at older (sighted) adults found. Wearable hazard devices found are BLV-targeted: NOA, Strap Ara, .lumen, Glide (handheld), LiDAR phone apps. [INFERENCE from the searches above]

## Could not read (blocked)

- applevis.com (Cloudflare; mail.applevis.com mirror works), support.letsenvision.com (403), mspoweruser.com (403), onmsft.com (403), vi.ie (403), macobserver.com (403), nypost.com (blocked), doubletaponair.com (SSL error), groups.io (402). Seeing AI "User Manual" PDF is regulatory labelling only.
