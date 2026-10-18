# Marco Polo: pain points, prior work, and feature ideas

> Historical research and proposed features, compiled before implementation. Product descriptions reflect the source dates, not a current exhaustive comparison. Use [the roadmap](../../docs/HACKATHON-ROADMAP.md) and [STATUS.md](../../STATUS.md) for Marco's implemented scope. This survey does not establish novelty or Marco's performance.

Compiled 2026-10-14. Read-only web research. Raw fetched text for most sources is in
`poc/research/pain_points_src/` (not in the repository) (filenames noted as [src: file]).
Verification tags: [VERIFIED] = quote read in the fetched page/PDF; [SNIPPET] = seen only in a search-engine
snippet, page not fetched (403 or not attempted); [INFERENCE] = my reasoning, not a sourced claim.

---

## Key takeaways

1. **Locating things is a large, recurring, unsolved part of blind life.** Be My Eyes' co-founder (who is visually impaired) says he uses it "regularly around the house, mainly to locate things I have dropped or [when I] have forgotten where I put something." Be My Eyes now handles 43M+ AI and video requests a year. Blind Redditors describe 20-minute hands-and-knees searches for a ring that was "back left of my left foot", and items that stay lost "for six months".
2. **Memory needs explicit evaluation.** Compare live object search with a saved last-seen location, then test persistence and relocalization. This survey cannot establish that every other tool lacks those features.
3. **Describing a location is not the same as guiding someone to it.** NaviSense P11: "Be My AI says it is there on the table, but it doesn't tell me where the remote is." Be My AI took 48 s of search time per object, against 16 s for audio-haptic guidance.
4. **What people lose (quantified).** In ORBIT (77 blind/low-vision collectors, 486 objects), the biggest clusters were remotes, keys, wallets/purses, guide canes, doors, AirPods/headphones, phones, watches and sunglasses. In the Pixie 2017 general-population survey, the weekly losses were TV remote 45%, phone 33%, keys 28% and glasses 27%. That is the same list, which is the curb-cut argument.
5. **"Someone moved it" is a pain point on its own.** Etiquette guides (APH VisionAware: "don't move things without asking; always put things back") and hotel housekeeping both break blind users' location memory. One blind travel writer does a "tactile reset" after cleaning: "Is my cane still where I propped it?" In the general public, 63% blame someone else for a lost item, and 1 in 3 couples argue about it. In dementia, missing items turn into accusations of theft.
6. **Coping today means systematic hand or cane sweeps, a fixed "home" for every item, asking a sighted person, Siri/HomePod pinging the phone, or Be My Eyes.** Training starts with "listen to hear where it lands". A drop-detection feature that does this listening for you is a direct fit.
7. **Spatial audio works, but continuous beacons and blocked ears are the top complaints.** Loomis 2005: spatialized repeated speech was fastest and best rated, but there were "many negative comments about the headphones ... blocking environmental sounds" and complaints about "continuous presence of tones". A Soundscape user muted the beacon because "the constant sound was making me nervous" and "I couldn't really tell where the sound was coming from." Design implications: a sparse on-demand "Polo", AirPods Transparency mode, and a haptic fallback.
8. **Prior work covers object search, memory and spatial guidance.** The papers and products below provide research context. Measure Marco's behavior directly; this survey does not establish a unique feature combination or limitations shared by all other systems.
9. **Best demo moments for a 36-hour build:** (a) drop keys, hear "Polo" from the floor where they landed; (b) a teammate moves the mug, and Marco says "your mug was moved from the desk; last seen on the shelf"; (c) nod to confirm "guide me there?"; (d) at the door, "you don't have your keys; they're on the couch."
10. **Voice-first and hands-free is required, not optional.** Seeing AI review: "how do the developers expect a blind person to touch the screen?" NaviSense D3: participants "strongly preferred natural voice interaction." Apple's 2026 accessibility preview moves Live Recognition onto the Action button. Use App Intents/Siri, the Action button and head gestures.

---

## 1. Blind/low-vision pain points in finding objects

### 1.1 Scale and quantification

- **VizWiz Social (Brady et al., CHI 2013).** "5,329 blind users asked 40,748 questions." Of 1,000 coded questions: "Identification questions were most common, making up 41% ... Description questions (24%) ... 17% of the questions were Reading questions." Medicine was 2% of identification and currency 1%. "Most of the photographs focused on members of the Object category (76%)." Important limitation: VizWiz only covers challenges "that can be represented with a still photograph," while those "requiring conveying and/or receiving continuous information, are beyond the bounds". Finding and guiding is exactly that continuous kind of task, so it is under-counted. [VERIFIED; src: brady2013.txt] https://www.cs.cmu.edu/~jbigham/pubs/pdfs/2013/visualchallenges.pdf (also https://dl.acm.org/doi/10.1145/2470654.2481291)
- **Be My Eyes scale.** "750,000 people, 8.3 million sighted volunteers, 43 million user requests a year"; "Be My AI now serves millions of requests every month." [VERIFIED; src: bme10.txt] https://www.bemyeyes.com/blog/be-my-eyes-celebrates-10-years-and-a-decade-of-accessibility-innovation/
- **Be My Eyes use case.** Co-founder Hans Jorgen Wiberg uses it "regularly around the house, mainly to locate things I have dropped or [when I] have forgotten where I put something." "Total calls answered by Be My Eyes Volunteers in 2022 was 882,186." [VERIFIED; src: pcmag_bme.txt] https://www.pcmag.com/how-to/be-my-eyes-how-to-help-a-visually-impaired-person-from-your-smartphone
- **ORBIT dataset (Massiceti et al., ICCV 2021).** 3,822 videos of 486 objects from 77 blind/low-vision collectors. "The largest clusters contained different types of remotes/controls, keys, wallets/purses, guidecanes, doors, airpods, headphones, mobile phones, watches, sunglasses and Braille readers." Cluster 1 was keys, 2 remotes, 3 wallets, 4 canes, 5 AirPods. [VERIFIED; src: orbit.txt] https://arxiv.org/abs/2104.03841
- **Teachable recognizers (Kacorri lab).** "Teachable object recognizers provide a solution for a very practical need for blind people - instance level object recognition. They assume one can visually inspect the photos they provide for training, a critical and inaccessible step for those who are blind." [VERIFIED abstract] https://pubmed.ncbi.nlm.nih.gov/36916963/ (Hong et al., ASSETS 2022)
- **Microsoft Find My Things.** Co-designer quote: "Losing my bus pass means I can't go anywhere. Losing my house key means I can't get home. Because these items are small and I use them daily, it's not unusual for me to lose track of them." [VERIFIED; src: findmythings_story.txt] https://www.microsoft.com/en-us/research/story/find-my-things/
- **NaviSense formative study (12 participants with visual impairments, ASSETS 2025).** "People with visual impairments (PVI) often struggle to independently locate and retrieve everyday objects ... frequently necessitating external assistance." [VERIFIED; src: navisense.txt] https://arxiv.org/abs/2509.18672

### 1.2 Dropped items

- r/Blind, "Has anyone searched for twenty minutes just for something to be next to them" (score 57): "I dropped my ring in my room and I just spent twenty minutes searching for it on my hands and knees for it to be back left of my left foot this whole time." Replies: "15 minutes? Sometimes this happens for six months." / "I've been blind for four years now and I haven't gotten any more skilled at recovering displaced or misplaced or newly placed objects." / "when I search for my earbuds case on the table ... hand knocks it down." [VERIFIED; src: reddit_threads1.txt] https://www.reddit.com/r/Blind/comments/1k9cnsw/
- r/Blind, "I just dropped my favorite piece of jewelry and can't find it": "So now I'm crying." The poster used Be My Eyes and "we searched but couldn't find it." The original poster had first hung up out of nervousness: "I keep telling myself that since I'm legally blind ... it's not for me." The item was never found. [VERIFIED] https://www.reddit.com/r/Blind/comments/mrbl9e/
- NaviSense Scenario 1, "Finding Dropped Keys": Brian "hears the faint sound of something falling ... having missed the direction of the sound, he has no idea where they landed. Without assistive tools, Brian might crouch and sweep the floor with his hands." Find My Things/AIGuide "require the object to be pre-scanned and labeled in advance; a limitation when the object, like Brian's keys, was not previously registered." [VERIFIED] https://arxiv.org/html/2509.18672
- Coping technique (Hadley): "when you drop something, listen to hear where it lands ... on a carpeted surface, things will be harder to hear ... If the object did roll away from you, point your toes in the direction that it dropped." [VERIFIED; src: hadley_dropped.txt] https://hadleyhelps.org/workshops/o-m-basics-series/finding-things-you-ve-dropped
- Guide Dogs UK: "If you drop an item, stop immediately and listen for the sound it makes as it lands. Turn to the direction of the sound. Use the spiral search technique." [VERIFIED] https://www.guidedogs.org.uk/getting-support/information-and-advice/life-skills/getting-around-safely/locating-dropped-items/
- Blind Girl Blogs: "the search for dropped objects ... a game of 'cat and mouse' ... crouching down, placing both hands flat on the floor ... accidentally fling it further away." [VERIFIED] https://blindgirlblogsapp.wordpress.com/2023/06/04/the-art-of-finding-lost-objects/

### 1.3 Items moved by others

- APH VisionAware: "When visiting someone who is blind or low vision, don't move things without asking; always put things back where you found them." [VERIFIED; src: aph_etiquette.txt] https://aphconnectcenter.org/visionaware/new-to-vision-loss/meeting-guiding-and-orienting-a-person-who-is-blind-or-low-vision/
- WSU etiquette PDF: "Tell them when you have brought new items into their environment, describing what they are, and most importantly, where you have put them ... do not move items ... after their positions are known." [SNIPPET] https://s3.wp.wsu.edu/uploads/sites/2111/2018/06/UPDATED-Etiquette-for-Interacting-with-People-Who-Are-Blind-or-Visually-....pdf
- Hotel housekeeping (Blind Travels): "I'm blind, and I organize my room in a specific way to find things. It would be super helpful if the cleaning staff could please not move my personal items." and "Tactile Reset After Cleaning ... Is my cane still where I propped it by the closet? Is the TV remote back on the dresser (or did it get placed on the TV stand)?" [VERIFIED; src: hotel_bt.txt] https://www.blindtravels.com/hotel-hacks-for-blind-and-low-vision-travelers/
- Family members: "I shout '<Insert child's name> where's my <thing>?' and the item usually appears in my hand"; "my daughter wanted to use my phone ... she was gone. I had to hunt her down." [VERIFIED] https://www.reddit.com/r/Blind/comments/fjbv2r/
- A sighted partner complains the blind girlfriend "asks all the time for help finding ... where things are that she's left on the floor or table." [VERIFIED] https://www.reddit.com/r/Blind/comments/1mpjr9j/

### 1.4 Similar-looking items (spices, cans, meds, toiletries)

- NaviSense P5: systems "struggle to differentiate between similar items such as shampoo versus conditioner." P9: "With medicine bottles, especially the round ones, SeeingAI just doesn't work. It either misses the label or gives me something completely wrong." P4: "to identify food, say, brown rice or white rice, I have to try three different apps." [VERIFIED] https://arxiv.org/html/2509.18672
- Hotel toiletries: "a row of mysterious small bottles – shampoo, conditioner, lotion… and they all feel identical." [VERIFIED] (Blind Travels, above)
- NFC labelling guide: "Two identical cans, two similar pill bottles, a drawer of black socks." [SNIPPET] https://nfcore.app/guides/nfc-tags-blind-low-vision-labeling
- Brady 2013: medicine accounted for 2% of identification questions and bathroom products for 6% of photo subjects. [VERIFIED]

### 1.5 Keys / phone / remote / glasses / cane

- Phone on a black chair: "that black case on my black chair means its invisible until I give up searching." Glasses: "I've done that with my glasses. Sitting right on my face." [VERIFIED] https://www.reddit.com/r/Blind/comments/1k9cnsw/
- Cane: "I on occasion lean it against a shelf in the store and walk away from it ... I have lost it at CVS and Trader Joe's." Another user uses a Sharper Image key finder on the cane. Another: "there's a tendency for me to prop it up against the wall or leave it." [VERIFIED] https://www.reddit.com/r/Blind/comments/1ufkhr1/
- Remote: NaviSense P11 (quoted above). ORBIT cluster 2 is remotes.

### 1.6 Unfamiliar places (hotels)

- "ask the hotel staff to provide you with a visual description and layout of your room ... plug sockets." [VERIFIED; src: hotel_bgb.txt] https://blindgirlblogsapp.wordpress.com/2023/05/31/top-5-hotel-tips-for-blind-travellers/
- "Bed in the center, bathroom to the left, thermostat on the right wall" / "Walk the room's perimeter ... I imagine a clock face over the room" / "I'll snap a series of reference photos of the room ... Later, I can use Seeing AI ... to review these." [VERIFIED] Blind Travels (above)
- Clew (Olin) exists because returning to a seat is hard: Clew is "designed with finding your way back to a seat or a table in mind and works best indoors over relatively short distances." [SNIPPET] https://github.com/occamLab/Clew

### 1.7 Coping strategies today

- Fixed homes for things: "I have specific places I put things ... on the right-hand side of my desk, or on the counter to the left of the Kuerig ... I'm only looking in 3 distinct places." / "I always put things back in the same place." [VERIFIED] https://www.reddit.com/r/Blind/comments/fjbv2r/
- Placing things deliberately: "leaving things on the edge of surfaces, or near objects that have a typical place, like my pillow." [VERIFIED] https://www.reddit.com/r/Blind/comments/1k9cnsw/
- Phone pinging: Apple Watch ping, iCloud Find, "hey Siri play music", HomePod, Alexa. Grid or clockwise search. "If I cannot find something within like 24 hours I either ask for help ... or I consider it lost forever." [VERIFIED] (fjbv2r)
- Vacuum with pantyhose over the nozzle; a flashlight flat on the floor (residual vision); Be My Eyes. [VERIFIED] (mrbl9e)

---

## 2. Frustrations with existing tools

All of the following find only what is in the camera view now. None of them remember.

- **Seeing AI, Find My Things.** You teach an item with "four short videos of the item ... from various angles," then "uses their phone to scan the environment ... until the tool locates the object," with guidance "to within arm's reach." [VERIFIED; src: findmythings_story.txt] Problems:
  - It needs each item registered in advance (NaviSense: "rely on object pre-registration and struggle in dynamic environments").
  - You have to sweep the camera.
  - It only works for items you thought to teach.
  - App Store: "the find my things feature is kind of broken for me ... I clicked on what I named it and it closed the app" (4 stars, 2024-04-10).
  - App Store: "how do the developers expect a blind person to touch the screen for functionality? Siri commands do not process a scene without touching the screen" (1 star, 2024-01-07). [VERIFIED; App Store RSS, src: appstore/] https://apps.apple.com/us/app/seeing-ai/id999062298
  - Design lesson from its co-designers: vibration is "very beneficial for people like me who are deaf-blind, but also for others who ... feel self-conscious if their phone starts talking at high volume in a public place." [VERIFIED]
- **Google Lookout Find mode (beta, 2024).** "Select from seven categories of items — like seating and tables or bathrooms — then as you move your camera around the room, Lookout will notify you of the direction and distance." It covers fixed categories only, not your keys, and is Android only. [VERIFIED; src: google_gaad2024.txt] https://blog.google/company-news/outreach-and-initiatives/accessibility/ai-accessibility-update-gaad-2024/
- **Apple Magnifier Detection Mode and Point and Speak.** It detects people, doors and furniture, and needs LiDAR [SNIPPET, Apple Support https://support.apple.com/en-gb/guide/iphone/iph35c335575/ios]. Point and Speak reads text you point at on appliances [VERIFIED snippet, Apple Newsroom 2023]. The 2026 update: "VoiceOver users can press the Action button on iPhone to quickly ask a question about what's in the camera viewfinder ... ask follow-up questions in their own words." [VERIFIED; src: apple_2026_a11y.txt] https://www.apple.com/newsroom/2026/05/apple-unveils-new-accessibility-features-and-updates-with-apple-intelligence/. On visionOS, "Live Recognition ... find objects" [VERIFIED; src: apple_2025_a11y.txt]. Apple is clearly heading toward voice-plus-camera Q&A, but with no persistent object memory and no spatial-audio guidance (as of this research).
- **Be My Eyes / Be My AI.**
  - Volunteers can fail too: the jewelry search above went unresolved.
  - There is social cost and hesitancy ("I just got nervous and hung up").
  - Be My AI "provided useful scene-level descriptions but lacked spatial specificity, often leading to information overload." It had the slowest search time in NaviSense: 48.2 s (Be My AI), 21.5 s (Meta glasses), 15.9 s (NaviSense). Accuracy: 85.7%, 55.9%, 95.4%. [VERIFIED] https://arxiv.org/html/2509.18672
- **Aira.** NaviSense P4: "It was frustrating when I tried using Aira volunteer with a microwave; the volunteer had a hard time navigating me to the start or cancel button." Remote assistance is "limited by availability, cost, and privacy concerns." [VERIFIED]
- **Ray-Ban Meta.** "lacked response consistency." P6: "Even after taking several pictures with Meta Glasses, I still couldn't locate the buttons." The "where you parked" reminder is explicit and spoken-only. Mashable: "there's a bit of irony in needing to remember to ask it in the first place." [VERIFIED NaviSense; SNIPPET Mashable https://me.mashable.com/tech/47003/]
- **Envision (glasses/app) Find Objects.** "Choose objects from a predefined list to have an audio cue play when the object is in front of the camera." [SNIPPET; support page returned 403] https://support.letsenvision.com/hc/en-us/articles/8118337733009-Find-Objects
- **AirTag Precision Finding with VoiceOver** (AppleVis review) [VERIFIED; src: av_airtag.txt] https://www.applevis.com/blog/apple-airtag-review-simple-setup-use-deliver-super-easy-accurate-finding-misplaced-items
  - Works well: "VoiceOver announces whether the AirTag is ahead of you; behind you; to your left; or to your right, along with its distance ... 'nearby', and then 'Here' ... haptic feedback, which increases in intensity."
  - Frustrations:
    - Range: "hit and miss at anything more than 30-35 feet" (20-25 ft across floors).
    - Calibration: "can often take up to 30 seconds."
    - Floors: "can't ... tell you if the AirTag is on the same floor."
    - Coarse directions: VoiceOver gets only 4 directions, "aren't currently as accurate as ... the augmented reality view."
    - Size: "can't imagine using one with ... AirPods or an Apple TV remote."
    - A tag is needed per item.
    - Elderly setup friction: "AirTags can't be setup without a) an iphone code and b) two-factor authentication" [VERIFIED] https://www.reddit.com/r/Blind/comments/1e0rnp1/
- **Soundscape retirement and successors.** The original app was pulled from the App Store in Jan 2023 and stopped working mid-2023. "My students were disappointed when SoundScape was discontinued." [SNIPPET r/Blind 14tdgad] / "I honestly don't know what to do come June and the app leaves my phone" [VERIFIED 103o2rv]. Successors: VoiceVista, Soundscape Community, and Scottish Tech Army's Soundscape [VERIFIED GDUK, src: gduk_voicevista.txt]. They are outdoor/GPS-scale and cannot guide you to keys on a table. AppleVis user: "I can't see the point of adding anything else when the descriptions all look the same." [VERIFIED; src: av_soundscape.txt]
- **NaviLens.** It needs printed codes installed in the environment: "Reading distance 100 ft ... Capture angle 160°." [VERIFIED; src: navilens.txt] https://www.navilens.com/en/. It is great for transit signage, but no one tags their keys with it.
- **Clew (Olin).** Records an ARKit path and guides you back to it with voice, sound or haptics [SNIPPET]. You must remember to start recording, and it tracks you, not your objects. Local copy of the related Olin participatory-design paper: papers/vio/olin_participatory_2024.txt, which reports 67 online and 11 in-person BVI co-designers.

---

## 3. Soundscape beacon feedback, blocked ears, spatial audio vs speech

- **Beacon design (Microsoft).** "rat-a-TAT, tat-tat ... Move directly toward the destination, and the audible cue becomes more overt, with a higher-pitched 'ting, ting, ting.'" Sighted teens said "listening to the beat helped me focus" and suggested it for ADHD, PTSD and anxiety. That is a curb-cut signal. [VERIFIED; src: telltale.txt] https://news.microsoft.com/features/the-telltale-tap-soundscape-app-brings-3d-audio-map-to-pedestrians-gaining-fans-well-beyond-those-with-vision-loss/
- **Head tracking.** Soundscape "now features head tracking with the Apple AirPods Pro and AirPods Max. Place your phone in your pocket ... Your AirPods will track the direction of your head." [VERIFIED; src: ss_features.txt] https://www.microsoft.com/en-us/research/product/soundscape/features/
- **User complaints (Equal Entry review by a blind user).** "As soon as I said the beacon, Soundscape began playing a constant rhythmic sound ... However, I couldn't really tell where the sound was coming from ... I like to be hyper-aware of my surroundings when I walk by myself, and the constant sound was making me nervous. Thankfully, there is an option to mute the beacon." [VERIFIED; src: equalentry_ss.txt] https://equalentry.com/microsoft-soundscape-a-user-review-by-sofia-gallo/. The review describes the original phone-heading Soundscape, before head tracking [INFERENCE from the 2018 date].
- **VoiceVista change.** "Manually toggling beacon audio effect now disables auto ... beacon sound effects will automatically unmute when you ..." (the auto-mute/unmute behaviour was a user-requested fix) [VERIFIED; src: voicevista.txt] https://drwjf.github.io/vvt/index.html. GDUK: the beacon noise "will stop when you take a wrong turn". [VERIFIED]
- **Headphones blocking the environment.**
  - Loomis et al. 2005 (15 legally blind participants): "There were many negative comments about the headphones ... blocking environmental sounds"; "Several complained about the continuous presence of tones"; yet "virtual speech—led to the shortest travel times and the highest subjective ratings, despite concerns about the use of headphones." [VERIFIED; local papers/psychoacoustics/loomis2005_jvib/pmc.txt] https://pmc.ncbi.nlm.nih.gov/articles/PMC2801896/
  - Walker & Lindsay 2005 (SWAN): visually impaired testers said "no matter how good the system was, they would not give up access to other auditory stimuli by wearing headphones." [VERIFIED; notes/psychoacoustics/q4q5_beacons_supernormal.md]
  - NaviSense: non-verbal audio "may falter in noisy settings." [VERIFIED]
- **Spatial audio vs speech.**
  - Loomis 2005: spatialized speech was fastest (6 fastest participants: virtual speech 70.7 s, virtual tone 86.4 s, body pointing 92.3 s) and best rated.
  - NaviSense users loved non-verbal hot/cold pulses: "The beeping sound, I love that. It's like that game you know, you're hot, you're cold" (P7). Also "left or right, up or down, and then bullseye, boom" (P3), and "occasional confusion when feedback was delivered too quickly."
  - Conclusion: a spatialized non-verbal "Polo", plus brief speech for landmark and distance on demand. [VERIFIED for the quotes; synthesis is INFERENCE]

---

## 4. General population: the curb-cut market

- **Pixie Lost and Found survey, 2017** [VERIFIED; src: pixie.txt] https://www.prnewswire.com/news-releases/lost-and-found-the-average-american-spends-25-days-each-year-looking-for-lost-items-collectively-costing-us-households-27-billion-annually-in-replacement-costs-300449305.html
  - "Americans spending 2.5 days a year looking for misplaced items"; "$2.7 billion each year replacing items."
  - Lost at least once a week: "TV remotes (45%), phones (33%), car & keys (28%), glasses (27%), shoes (24%) and wallets/purses (20%)."
  - "more than 60% of people admitting they have been late to work or school"; "almost half ... missed an appointment."
  - "one in three ... get in fights with their significant other"; "63% fessed up to blaming someone else."
  - "Millennials are generally TWICE as likely to misplace items over Boomers."
  - First places people look: "purse or bag (21%), followed by the couch (18%), pockets of the previous day's clothing (14%)."
  - Caveat: this is a vendor survey; methodology and sample size are not given in the press release.
- **ADHD.** "Often loses things; is forgetful and disorganised in daily activities" (listed symptom). [VERIFIED; Wikipedia ADHD page] https://en.wikipedia.org/wiki/Attention_deficit_hyperactivity_disorder. The DSM-5 inattention criterion "often loses things necessary for tasks or activities (e.g., ... keys, wallets, eyeglasses, mobile telephones)" is not verified in this session.
- **Older adults and dementia.**
  - "Searching for misplaced household items is a common experience and is an early sign of dementia ... Retrieval technology is in its early phase of development." [VERIFIED abstract; src: helpmefindit.txt] Help me find it! scoping review, J Ambient Intell Humaniz Comput 2026, https://link.springer.com/article/10.1007/s12652-026-05122-2
  - Alzheimer's Society: "If the person thinks an item should be somewhere and it's not, this may lead them to think that someone is hiding or stealing things from them ... It can also be frustrating if you have to spend time finding things." [VERIFIED; src: alzsoc.txt] https://www.alzheimers.org.uk/about-dementia/stages-and-symptoms/dementia-symptoms/hiding-hoarding-losing
  - TROUVE project: "Older adults with cognitive impairment are significantly more affected by this problem. It is a source of frustration, anxiety, interpersonal conflict and disability ... Informal caregivers are greatly impacted." [SNIPPET] https://www.sciencedirect.com/science/article/pii/S1959031816000269
  - MemPal (MIT): "Older adults have increasing difficulty with retrospective memory ... posing stress on caregivers." [VERIFIED abstract] https://arxiv.org/abs/2502.01801
- **Caregivers and partners.** Sighted partners of blind people are asked "where things are that she's left on the floor or table" [VERIFIED, Reddit 1mpjr9j]. A shared household memory takes this load off caregivers.

---

## 5. Novelty check: prior work on "remember where it is and guide me back"

Prior work, ordered from closest to Marco Polo to least close:

- **NaviSense (Penn State/USC, ASSETS 2025).** Conversational LLM, then VLM open-world detection, then AR+LiDAR localization, then audio-haptic guidance. "Requires line-of-sight interaction and steady phone handling ... relies on cloud-based models, raising privacy and connectivity concerns." No memory. [VERIFIED] https://arxiv.org/abs/2509.18672
- **Making Objects Speak (Qin et al., IEEE/SICE SII 2026).** "localize and reach objects using spatialized audio cues, rendered as if the objects themselves emit sound ... voice command recognition, RGB-D-based 3D localization, and head-tracked spatial" audio. This is essentially the Polo metaphor for objects already in view, for grasping. No memory. [SNIPPET; IEEE page not fetchable] https://ieeexplore.ieee.org/document/11404455
- **ObjectFinder (Liu, Guo et al., IJHCI 2026).** "wearable prototype with smart glasses (RGB-D sensing), a bone conduction headset," open-vocabulary search and navigation, aimed at unfamiliar scenes. [SNIPPET] https://arxiv.org/abs/2412.03118
- **MemPal (MIT Media Lab, IUI 2025).** Wearable camera, then a multimodal-LLM "real-time automated text diary," then a voice answer. Tested with "N=15 older adults within their own homes that showed improved performance of object finding with audio-based assistance." The answer is verbal or textual, with no 3D anchoring or spatial guidance. [VERIFIED abstract] https://arxiv.org/abs/2502.01801
- **GO-Finder (Yagi et al., IUI 2021).** "registration-free wearable camera ... automatic discovery of hand-held objects ... visual timeline ... retrieve the last appearance." The output is visual, for sighted users. Its key insight, that registering items is "a cumbersome burden ... cannot help remind them of unexpectedly lost objects," supports Marco Polo's passive approach. [VERIFIED abstract] https://arxiv.org/abs/2101.07314
- **Lost & Found (ETH/Microsoft, RA-L 2025).** Project Aria egocentric recordings, then tracking of 6DoF pose changes of moved objects in a 3D scene graph. It is a robotics demo (retrieving an object hidden in a drawer). Relevant to "someone moved it" and putting things in drawers. [VERIFIED; src: lostfound.txt] https://behretj.github.io/LostAndFound/
- **QaEgo4D, "Where did I leave my keys?" (CVPRW 2022).** Episodic-memory video QA benchmark. The answer is text ("on the table"). [SNIPPET] https://openaccess.thecvf.com/content/CVPR2022W/Ego4D-EPIC/html/Barmann_Where_Did_I_Leave_My_Keys_-_Episodic-Memory-Based_Question_Answering_CVPRW_2022_paper.html
- **Google Project Astra (I/O 2024).** On a phone, "asked Gemini 'do you remember where you saw my glasses?'" The answer was verbal; the demo was sighted. [SNIPPET; Engadget, Axios] https://www.axios.com/2024/05/15/google-ai-search-find-glasses
- **Ray-Ban Meta "remember where I parked" (Connect 2024).** Explicit reminders and a verbal answer: "You're parked in lot 19 A." [SNIPPET] https://about.fb.com/news/2024/09/ray-ban-meta-glasses-new-ai-features-and-partner-integrations/
- **Brilliant Labs Halo / Noa.** A "Narrative" memory system that enables "Where did I leave my car keys?" Glasses, verbal answers. [VERIFIED; src: eejournal.txt] https://www.eejournal.com/article/aiar-glasses-that-remember-where-you-left-your-keys/
- **Envision with Aria Gen 2.** "used the on-device SLAM capabilities of Aria Gen 2, along with spatial audio ... to assist blind and low-vision individuals seamlessly navigate indoor environments ... still in the exploratory and research phase." Navigation, not object memory. [VERIFIED; src: aria_gen2.txt] https://www.meta.com/en-gb/blog/project-aria-gen-2-next-generation-egocentric-research-glasses-reality-labs-ai-robotics/
- **AnchorThis (App Store).** "Say 'I put my passport in the gray lockbox in the office,' then ask for it." Manual voice entry, text answers, no vision. [VERIFIED; src: anchorthis.txt] https://apps.apple.com/us/app/anchorthis-ai-finds-my-things/id6800138617
- **Pixie (2017).** AR tags that "SHOW the location of misplaced objects." Needs hardware tags and is visual. [VERIFIED]
- **Vision Pro.** No known app does passive object memory. visionOS Live Recognition can "find objects" in view [VERIFIED]. Vision Pro itself "lacks Find My" [SNIPPET, The Verge].
- **Not object memory:** Project Daredevil (MIT Assistive Technology) does iPhone LiDAR plus AirPods depth sonification ("digital echolocation"). [VERIFIED README]

**Questions to evaluate in Marco** [research directions, not validated claims]:
1. Do registered items and usable map associations survive a restart and relocalization?
2. Can a user follow guidance to a remembered point when the item is out of view, while understanding that the item may have moved?
3. Do head-tracked cues help with turning, walking and final hand placement on the physical setup?
4. Do observed moves and left-behind events remain accurate under occlusion and tracking loss?
5. Do voice commands, VoiceOver and status feedback support the intended blind-user flow?

Treat persistence, accessibility and false-positive performance as testable requirements. Do not infer superiority from a feature list.

---

## 6. Feature ideas, ranked

Impact = for blind/low-vision users. Effort = for a 36-hour team that already has ARKit, LiDAR, AirPods head-tracking and a VLM pipeline (low = under 4 h, med = 4-10 h, high = over 10 h). Wow = live demo impact for judges. Ranking is by impact/effort with a demo-value bonus. All ratings are [INFERENCE].

| # | Idea | Pain point + source | Impact | Effort | Wow |
|---|------|---------------------|--------|--------|-----|
| 1 | **Core: passive "last seen" memory and "Marco, where are my X?" with head-tracked Polo from the 3D point; "Here" at arm's reach** | Tools only find what is in view or pre-registered (NaviSense; Find My Things story); ORBIT top items: keys, remotes, wallets, canes, AirPods | Very high | Med (base build) | High |
| 2 | **Put-down confirmation.** When an object leaves the hand, say softly "keys: kitchen counter, left of the fruit bowl" (VLM landmark); doubles as the memory write | Be My AI "doesn't tell me where the remote is" (NaviSense P11); Soundscape's value is landmark callouts; builds trust in the memory | High | Low | Med |
| 3 | **Dropped-item detection.** SoundAnalysis/mic transient plus "object left hand" plus floor LiDAR, then "Sounds like something fell. Polo" from the landing spot. Fallback: "Marco, I dropped something" scans the last 3 s of floor frames | Coping today is "listen to hear where it lands" (Hadley, GDUK); 20-minute ring search (r/Blind 1k9cnsw); NaviSense "Brian's keys" | Very high | Med-high | **Very high (top demo moment)** |
| 4 | **"Someone moved it."** Diff the new sighting against the last: "Your mug was moved from the desk at 3:12 to the shelf," plus a who/when timeline | APH "don't move things"; hotel housekeeping "tactile reset" (Blind Travels); 63% blame others (Pixie); dementia theft accusations (Alzheimer's Society) | High | Low-med (just the memory log) | High |
| 5 | **Nod to confirm / shake to cancel** via CMHeadphoneMotionManager ("Guide you there? nod") | Hands are busy; "how do the developers expect a blind person to touch the screen" (Seeing AI review) | Med-high | Low | **Very high** |
| 6 | **Siri / App Intents / Action button / back-tap entry** ("Hey Siri, ask Marco where my keys are") | NaviSense D3: "strongly preferred natural voice interaction"; Apple 2026 Live Recognition on the Action button | High | Low-med | Med |
| 7 | **Haptic Polo** (phone and/or Apple Watch hot-cold pulses) for noisy places, DeafBlind users, or no earbuds | Find My Things co-designer: vibration "very beneficial for people like me who are deaf-blind"; NaviSense audio "may falter in noisy settings" | High | Low | Med |
| 8 | **Transparency-friendly beacon.** Sparse Polo (call then wait; faster when close), auto-mute when facing the target, AirPods Transparency on | "constant sound was making me nervous" (Equal Entry); "blocking environmental sounds" (Loomis 2005); VoiceVista auto-mute | High | Low | Low |
| 9 | **Leaving-home check.** An anchor at the front door; on approach, "You don't have your keys; they're on the couch. Polo" | Pixie: over 60% late due to searching, keys 28% weekly; r/Blind "home" strategy | High | Med | High |
| 10 | **Item homes.** "Marco, this is where my keys live"; then "keys are not home; last seen in the bathroom" | Fixed-home strategy (r/Blind fjbv2r, Blind Travels "Strategic Item Placement") | Med-high | Low | Med |
| 11 | **Find your cane / guide-dog gear** (cane as a default tracked item; "where did I lean my cane?") | ORBIT cluster 4 is canes; "lost it at CVS and Trader Joe's" (r/Blind 1ufkhr1); hotel "Is my cane still where I propped it" | High (emotional) | Low (another label; thin-object detection risk) | Med-high |
| 12 | **Which-one ID at pickup.** On arrival, a VLM reads the label: "this is ibuprofen; the Tylenol is the bottle to your right" | Meds and shampoo/conditioner confusion (NaviSense P5, P9); hotel toiletries; Brady medicine questions | High | Low-med | Med |
| 13 | **Hotel "hear the room."** One RoomPlan sweep; "Marco, around me" gives spatial callouts clockwise (door, bed, bathroom, outlet, thermostat); "Polo, bathroom" | Hotel orientation tips (Blind Travels clock-face method, Blind Girl Blogs); Soundscape "Around Me" model | High for travelers | Med | High |
| 14 | **Find a seat / door / back to my seat.** RoomPlan chairs/doors, or a "remember my seat" anchor (Clew-like) | Lookout Find defaults to "Seating & Tables"; Clew built for "a seat or a table" | Med | Med | Med |
| 15 | **Floor/room-aware answers** ("upstairs, in the bedroom") | AirTag "can't tell you if the AirTag is on the same floor" (AppleVis) | Med | Low (ARKit height plus room labels) | Low |
| 16 | **Timeline queries** ("when did I last have my wallet?" / "what did I put in the drawer?") | GO-Finder timeline; MemPal diary; dementia caregivers | Med | Low (log already exists) | Med |
| 17 | **Shared family memory** (a sighted housemate's phone also logs sightings; caregiver view) | Partners asked "where things are" (r/Blind 1mpjr9j); caregiver stress (MemPal, TROUVE) | Med-high | High (multi-device relocalization) | Med |
| 18 | **On-device / privacy mode** (no video leaves the phone; a blur/ignore list) | NaviSense: cloud "raising privacy and connectivity concerns"; scoping review: "Usability and privacy are not yet researchers' priorities" | Med (trust) | Med | Low |

**Suggested 36-hour scope** [INFERENCE]:
- Must-have: items 1, 2, 5, 7 and 8.
- Strongly recommended for the demo: 3 (drop; even a semi-scripted "I dropped something" path), 4 and 9.
- Stretch: 11, 12 and 13.
- Skip during the hackathon: 17 and 18. Put them on the vision slide.

**Demo script with the strongest moments:**
1. Walk past a table and put keys down; Marco quietly confirms the landmark.
2. A teammate secretly moves the mug; Marco announces it.
3. Drop the keys and get an immediate "Polo" from the floor.
4. Walk to the door and get the "You don't have your keys" warning.
5. Nod to accept guidance, follow the sound, and hear "Here".
6. Close: "The same app finds a sighted user's TV remote" (45% lose it weekly, per Pixie).

---

## Source index (local raw text)

- `pain_points_src/` contains: brady2013.txt, pixie.txt, findmythings_story.txt, orbit.txt, navisense.txt, bme10.txt, pcmag_bme.txt, google_gaad2024.txt, apple_2026_a11y.txt, apple_2025_a11y.txt, av_airtag.txt, av_soundscape.txt, equalentry_ss.txt, telltale.txt, ss_features.txt, voicevista.txt, gduk_voicevista.txt, navilens.txt, hadley_dropped.txt, gduk_dropped.txt, blindgirl.txt, hotel_bt.txt, hotel_bgb.txt, aph_etiquette.txt, alzsoc.txt, helpmefindit.txt, mempal_abs.txt, gofinder_abs.txt, lostfound.txt, daredevil_readme.md, aria_gen2.txt, anchorthis.txt, eejournal.txt, reddit_threads1.txt, reddit_threads2.txt, appstore/*.json, search*.txt
- Reused from earlier work: notes/psychoacoustics/q4q5_beacons_supernormal.md (Walker & Lindsay), notes/psychoacoustics/q8q9_guidance_haptics.md (Loomis 2005), papers/vio/olin_participatory_2024.txt (Clew/Olin co-design).
- Not obtained (blocked or paywalled): the Find My Things ASSETS 2023 PDF, Envision support pages (403), IEEE "Making Objects Speak" full text, the MDPI 2023 guidance-modality comparison (403), the TROUVE full text, and the CDC ADHD page.
