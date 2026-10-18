# POC 27: automatic room map on the dashboard (working notes, kept current)

**Goal (user, 2026-10-18):** the dashboard map draws the room itself, Tesla-style, instead of a rectangle:
- walls and boundaries;
- landmarks: tables, chairs, sofas, trees/plants.

Fun to look at, kept simple. **First, prove it doesn't cost detection accuracy, the 1 frame/s latency, or anything else.**

## What exists
- The server's `RoomMap` (`server/marco/world/roommap.py`): a 5 cm coloured voxel cloud from every frame's LiDAR, plus `floor_y()`.
- The dashboard's `MapView.tsx` **already draws `map.walls` (lines) and `map.fixtures` (table, sofa, storage)**. The adapter sends `walls: null` and no fixtures today.
  - Within the current schema, walls and table/sofa/storage need no frontend change.
  - Chairs and trees/plants need new kinds (Sandeep's code: `schema.ts`, `MapView.tsx`). Extra snapshot fields are tolerated: Zod strips unknown keys, and the JSON Schema has no `additionalProperties: false`.

## Plan
1. **Geometry only, from the voxels** (no new model): walls = tall occupied columns turned into line segments; tables = flat tops at 0.6–1.0 m; seats at 0.3–0.6 m (chair vs sofa by footprint); tall narrow objects = tree/plant/column.
2. **Optional semantic labels:** OWLv2 text queries ("tree", "chair", ...) reusing the frame's existing image pass. Measure the extra milliseconds, and check that item outputs are unchanged.
3. **Ground truth:**
   - synthetic room: exact walls and furniture;
   - ARKitScenes: real 3D furniture boxes;
   - iPhone venue clips: qualitative.
4. **Product risks to measure:**
   - frame latency with the summariser running alongside;
   - item detection unchanged (bitwise);
   - snapshot size;
   - memory as the map grows;
   - the summary is display-only, never used for guidance or speech.

## Findings (append as measured)

### 2026-10-18, pass 1: geometry only (server/marco/world/layout.py)
- **Design.**
  - `RoomMap.add` also fills a `ColumnGrid`: 10 cm columns × 10 cm height slices, counting frames per slice plus green frames, vectorised.
  - `summarize()`:
    - walls: Hough lines through "vertical" columns (a 0.6 m gap-free run reaching 1 m), split at 0.4 m gaps;
    - furniture: 4-connected parts per height band. Seat 0.30–0.62 m, table 0.62–1.15 m, tall. A bag on a table counts as the table.
    - backs: thin, ≥ 0.25 m higher than the seat, adjacent, covering ≥ 50 % of the seat side. Chair or sofa by width; bed if both sides ≥ 1.3 m.
    - backless seats: chair if ≤ 0.75 m both sides; low table if deep and ≤ 1.6 m wide; otherwise bench.
    - tall: green → tree or plant; near a wall → storage; free-standing (a person, a pole) → dropped.
    - occupancy: walls need 1 frame; furniture needs 2 frames (2 for walls lost half of them; 1 for furniture let emulator speckle merge objects).
  - The brain emits `room_layout` to the dashboard every 3 frames (`MARCO_LAYOUT_EVERY`) once the floor is known. A new `map_id` resets the RoomMap; before this, old-frame voxels lingered.
- **Harm checks (run.py), all 5 sessions:**
  - map points: bitwise identical to the old RoomMap;
  - `RoomMap.add` is faster than before (vectorised colours; synthetic 6.7 → 4.3 ms/frame);
  - grid add: 0.17–0.31 ms/frame;
  - `summarize`: 5–10 ms;
  - grid: 0.7–1.3 MB (cap 40 m × 40 m ≈ 14 MB);
  - layout JSON: 0.4–1.3 KB.
- **Accuracy (latest):**
  - synthetic room: walls 94 % precision, 91 % recall of the seen wall length; furniture 6/6 found, 6/6 right kind, median IoU 0.6, centre error 0.13 m.
  - ARKitScenes 41069021 (19 sparse frames): 6/17 found, 5 right kind. Most cabinets become walls (their fronts are vertical runs), and the sofa is called a table.
  - iPhone venue clips: no walls in LiDAR range in the 10–14 s clips. The round table with laptops and people is one table; chairs are found. Fountain stepping stones and ledges come out as low tables or benches. Trees and plants are never seen: 1 green voxel in rec1, because they're beyond 5 m.
- **User asked (mid-goal):**
  - "they should look like the shape they are; some reference shape … take reference from how a tesla screen is";
  - "is this how tesla does things … reasonably accurate mapping in reasonable latency".
  - Answer given: we copy Tesla's rendering (a stock shape per class at a pose). Tesla's perception is neural nets on cameras. Next step: OWLv2 text queries ("chair, table, sofa, plant, tree") on the same image pass (an extra head call, a few ms), voted onto the LiDAR parts. RoomPlan on the phone is the indoor alternative (iOS work; no trees).

### 2026-10-18, pass 2: harm checks, speed, and the dashboard drawing
- **No change to what Marco detects** (`harm.py`).
  - The real brain ran with the layout off (column grid and `room_layout` disabled, old `RoomMap.add`) and on, alternating off/on twice.
  - Every output except `room_layout` was identical: boxes, scores, placements, events, frame JPEGs, map points.
  - Sessions: fake-livingroom (truth detector), rec2-find (OWLv2 + DINOv2 with the real photos), arkitscenes (OWLv2 registered from truth crops).
  - Ignored when comparing: random ids and the pose-driven `world` snapshot, which is throttled by the wall clock.
- **Frame latency (Mac M3 Pro, inline layout):**
  - mean change: −6.7 to +1.4 ms (noise) on 375–396 ms OWL frames;
  - on the CPU-only synthetic run, p95 went from 14 to 23 ms: the 1 frame in 3 that computes a layout.
- **Scale (`scale.py`, the synthetic room tiled; `summarize` time):**
  - **first version:** 1 room 11 ms, 4 rooms 61 ms, 9 rooms 214 ms, 25 rooms 1.3 s, 40 × 40 m cap 3.1 s. That would have been real harm in a big venue.
  - **fix:** parts kept as bounding windows, not whole-grid masks; bincount Hough votes; overlap check pruned by distance.
  - **after the fix:** 5 / 16 / 38 / 129 / 177 ms.
  - The layout now runs on its own thread (`MARCO_LAYOUT_ASYNC`, default on). It reads a view of the grid and is sent with the first frame after it's ready, one at a time. A layout for a map that changed meanwhile is dropped.
  - Output is capped at the 200 biggest objects and 200 longest walls (about 40 KB at most).
- **Dashboard (frontend):**
  - `map.landmarks` added to `schema.ts`; kind and shape are strings, so a new kind can't break the snapshot parse.
  - `lib/roomShapes.ts` holds one stock shape per kind:
    - table: rect or round top;
    - chair: seat and back;
    - sofa: back, arms and cushions;
    - bench: slats;
    - bed: pillows and blanket;
    - shelf: front and doors;
    - tree: lobed canopy;
    - plant: leaves.
  - `RoomShape.tsx` draws a shape with a shadow that always falls the same way.
  - In `MapView`, scanned walls are bolder, landmarks are drawn, hand-placed fixtures get the same shapes (facing the map centre), and there's a "Scanned room" legend entry.
  - Previews come from the same TS code (`preview.ts`, `rsvg-convert`); see the report figures.
  - Prettier 3.9.6 (local npx cache): clean. TypeScript 6.0.3 (VS Code's) with real zod 4 types and stub React: 0 errors in the changed files.
  - vitest and Playwright are not run here (no node_modules on this Mac): Sandeep runs `npm run check`.
- **Server tests:** 111 passed (12 new).
