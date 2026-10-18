# Registration framing and square preprocessing evaluation

October 18, 2026. Evaluation only: no detector, threshold or registry changes.

Use a close-up photo of one fully visible object on a plain contrasting surface,
with identifying features visible, a small border, no competing objects, hand
occlusion or glare. One reference is stored per item; multiple uploads do not
automatically create a multiview reference. Caretakers need not take square photos.

Seven isolated registrations used the cached GPU models and existing photos,
without calling the application or saving registrations. The original Bottle
photo selected a tiny background region, about x688–727, y15–143. Focusing the
same photo to x320–880, y150–1330 selected the intended bottle, about x431–739,
y275–1185 in original coordinates. A tighter framing also worked; original and
focused Coffee/Pringles photos selected the intended objects. Registry checksums
were unchanged. Cropping saved photos simulates framing, not new lighting/views.
The bottle was already large and central: removing background competition matters.

The preprocessing comparison reused the 1,184-frame replay (baseline matched all
4,320 historical decisions). Select 16 equal frame-index bin midpoints per
session: 32 frames, 108 applicable item/frame checks. Excluding five uncertain
visual annotations leaves 103 checks and 18 identifiable visible targets.
Labels are assistant visual annotations, not independent human ground truth.
Prior investigation already examined this footage; this is not an unseen test.

Keep proposals and other gates fixed. Compare normal DINO center preprocessing
against square padding of both reference and candidate, using RGB (124,116,104),
then the same resize/center processor. Thresholds 0.377 and 0.469 came from POC 29
before this comparison; equal-threshold rows isolate the preprocessing effect.

| DINO input / threshold | Correct matches | False matches | Missed visible targets |
| --- | ---: | ---: | ---: |
| Current center / 0.30 | 3 | 11 | 15 of 18 |
| Current center / 0.38 | 3 | 3 | 15 of 18 |
| Square / 0.30 | 5 | 10 | 13 of 18 |
| Square / 0.38 | 4 | 6 | 14 of 18 |
| Square / 0.377 | 5 | 6 | 13 of 18 |
| Square / 0.469 | 3 | 2 | 15 of 18 |

Square/0.377 gains two correct matches and rejects six old false matches, but
introduces a new Bottle match on the wearer's vest. Only nine of 18 target
opportunities have a correct OWLv2 proposal; DINO cannot recover objects outside
that proposal. These are recognition decisions, not successful 3D placements or
audible finds. The placement filter changes only square/0.30, from ten to nine
false matches.

A separate Bottle-only oracle diagnostic substitutes the manually selected real
bottle reference: center/0.30 improves from zero correct/five false to three
correct/three false; square/0.377 then gives three correct/four false. Improving
registration and square preprocessing do not have automatically additive gains.
On previously selected examples outside the table, square/0.377 rejects the
Fanta-as-Coffee false match but loses a real Coffee match and keeps a chair-as-
Bottle false match. The exact wearer-reported clear-cup-as-Bottle instant remains
unconfirmed; do not equate the venue's different cups.

Validate the extracted registration crop first. Treat square/0.377 as a candidate
configuration, collect a fresh untouched recording after registration is fixed,
and freeze labels/settings before comparing again. Unknown look-alike rejection
remains unresolved. These would be object-agnostic code changes that survive
resetting the library; they have not been implemented by this evaluation.

Full report, labels, frame sheets, scores and reproducible scripts are in
`/private/tmp/marco-preprocessing-eval-20261018/`; replay and original investigation
are in `/private/tmp/marco-investigation-20261018-Hgw72c/`. Raw private recordings
remain outside Git. Few targets, correlated frames and imperfect annotations
limit generalization; these counts are not a product-level false-positive rate.
