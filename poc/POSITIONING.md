# Marco Polo: demo scope and limitations

The demo joins remembered object locations, spatial guidance and caretaker-provided labels. The current architecture is in [the roadmap](../docs/HACKATHON-ROADMAP.md); implemented behavior and verification are in [STATUS.md](../STATUS.md). Earlier competitive pitch notes are superseded.

## Demonstrate observed behavior

1. Register a distinctive object through Photon with a clear photo and typed name.
2. Let the phone observe it and establish a location in the current room map.
3. Ask for the object and follow the directional and distance cues.
4. Show the matching item, camera observation and last-seen information on the dashboard.
5. Exercise an unknown-item question and typed caretaker reply when both phones are available.
6. Move an item in camera view, then show the new observation. An item moving outside the camera's view cannot be tracked until it is seen again.

Use the actual app's cues rather than a scripted claim about what the wearer heard. Headphone output and physical hand guidance need device checks; browser Listen in is an observer reconstruction.

## Choose and test registration photos

Use one fully visible object, a plain contrasting background, good light and a close view that preserves its outline. Inspect the saved detector crop before relying on the registration. Transparent, tiny, obscured and visually similar objects remain useful stress tests; a clean demonstration is not evidence that those cases are solved.

Compare the same fixed, labeled footage when changing framing or preprocessing. Include absent-object frames, look-alikes, clutter, different distances and re-observation after movement. Report misses and false matches together. See [the registration evaluation](../docs/DETECTION-EVALUATION-20261018.md) for measured results and limits.

## Claims to keep bounded

- An isolated POC score does not establish a general recognition rate.
- A saved last-seen position is not confirmation that the object is still there.
- Identical-item identity, general unknown-object rejection and reliable transparent-object depth are unresolved.
- A successful software test or unsigned build does not prove AirPods perception, walking or touch performance.
- Raw session frames and registration media are stored privately; do not claim that the system stores no images.
- The prototype does not establish novelty or superiority over other assistive technology.

Technical prior work and source attribution remain in [research/landscape/products.md](research/landscape/products.md), [research/landscape/research.md](research/landscape/research.md) and the relevant POC notes. Historical experiments may include approaches outside the current demo.
