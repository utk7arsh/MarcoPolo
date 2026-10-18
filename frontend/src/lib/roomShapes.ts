// Reference shapes for the room map, drawn the way a car's screen draws the
// road: one stock shape per kind of thing (every chair looks like a chair),
// placed at the scanned position, size and facing. The server's room layout
// (map.landmarks) is LiDAR geometry, so the shapes say "about here, about this
// big", not an exact outline.
//
// Shapes are in local pixels: centred on (0, 0), `width` across, `depth` front
// to back, and the front facing up (-y). MapView rotates them by yawDeg, which
// uses the wearer's convention: 0 faces the map's top, 90 its right.

export type Tone =
  'base' | 'top' | 'detail' | 'line' | 'leaf' | 'leafTop' | 'trunk'

export type Shape =
  | {
      tag: 'rect'
      x: number
      y: number
      w: number
      h: number
      r: number
      tone: Tone
      shadow?: boolean
    }
  | {
      tag: 'ellipse'
      cx: number
      cy: number
      rx: number
      ry: number
      tone: Tone
      shadow?: boolean
    }
  | { tag: 'path'; d: string; tone: Tone; shadow?: boolean }
  | { tag: 'line'; x1: number; y1: number; x2: number; y2: number; tone: Tone }

export const TONES: Record<Tone, { fill: string; stroke: string }> = {
  base: { fill: '#e7e9ec', stroke: '#c4c9d0' },
  top: { fill: '#f3f4f6', stroke: 'none' },
  detail: { fill: '#d5d9df', stroke: '#bfc5cd' },
  line: { fill: 'none', stroke: '#c4c9d0' },
  leaf: { fill: '#d3e5ca', stroke: '#a9c99c' },
  leafTop: { fill: '#e4f0de', stroke: 'none' },
  trunk: { fill: '#bba78f', stroke: 'none' },
}

export const LANDMARK_LABELS: Record<string, string> = {
  table: 'Table',
  chair: 'Chair',
  sofa: 'Sofa',
  bench: 'Bench',
  bed: 'Bed',
  storage: 'Shelf or cabinet',
  tree: 'Tree',
  plant: 'Plant',
}

const clamp = (v: number, lo: number, hi: number) =>
  Math.min(Math.max(v, lo), hi)
const r1 = (v: number) => Math.round(v * 10) / 10

function rect(
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  tone: Tone,
  shadow = false,
): Shape {
  const rr = Math.min(r, w / 2, h / 2)
  return { tag: 'rect', x, y, w, h, r: Math.max(rr, 0), tone, shadow }
}

/** A scalloped circle: a tree's canopy seen from above. */
export function lobes(cx: number, cy: number, r: number, n: number): string {
  const at = (a: number, rad: number) =>
    `${r1(cx + rad * Math.cos(a))} ${r1(cy + rad * Math.sin(a))}`
  let d = `M${at(0, r * 0.82)}`
  for (let i = 0; i < n; i++) {
    const a0 = (2 * Math.PI * i) / n
    const a1 = (2 * Math.PI * (i + 1)) / n
    d += `Q${at((a0 + a1) / 2, r * 1.18)} ${at(a1, r * 0.82)}`
  }
  return d + 'Z'
}

function leaves(r: number, n: number): string {
  let d = ''
  for (let i = 0; i < n; i++) {
    const a = (2 * Math.PI * i) / n - Math.PI / 2
    const [cx, cy] = [Math.cos(a), Math.sin(a)]
    const [px, py] = [-cy, cx]
    const tip = `${r1(r * cx)} ${r1(r * cy)}`
    const c1 = `${r1(r * (0.55 * cx + 0.32 * px))} ${r1(r * (0.55 * cy + 0.32 * py))}`
    const c2 = `${r1(r * (0.55 * cx - 0.32 * px))} ${r1(r * (0.55 * cy - 0.32 * py))}`
    d += `M0 0Q${c1} ${tip}Q${c2} 0 0Z`
  }
  return d
}

/** The stock shape for one landmark. Unknown kinds get a plain block. */
export function landmarkShapes(
  kind: string,
  widthM: number,
  depthM: number,
  scale: number,
  round = false,
): Shape[] {
  const w = Math.max(widthM * scale, 4)
  const d = Math.max(depthM * scale, 4)
  const [x0, y0] = [-w / 2, -d / 2]
  switch (kind) {
    case 'table': {
      const inset = clamp(Math.min(w, d) * 0.12, 1.5, 5)
      if (round)
        return [
          {
            tag: 'ellipse',
            cx: 0,
            cy: 0,
            rx: w / 2,
            ry: d / 2,
            tone: 'base',
            shadow: true,
          },
          {
            tag: 'ellipse',
            cx: 0,
            cy: 0,
            rx: w / 2 - inset,
            ry: d / 2 - inset,
            tone: 'top',
          },
        ]
      return [
        rect(x0, y0, w, d, 5, 'base', true),
        rect(x0 + inset, y0 + inset, w - 2 * inset, d - 2 * inset, 3, 'top'),
      ]
    }
    case 'chair': {
      const back = clamp(d * 0.26, 2.5, 9)
      return [
        rect(
          x0 + w * 0.06,
          y0,
          w * 0.88,
          d - back * 0.5,
          w * 0.2,
          'base',
          true,
        ),
        rect(x0, d / 2 - back, w, back, back / 2, 'detail', true),
      ]
    }
    case 'sofa': {
      const back = clamp(d * 0.28, 4, 16)
      const arm = clamp(w * 0.09, 3, 12)
      const seatW = w - 2 * arm
      const n = clamp(Math.round(seatW / scale / 0.65), 1, 4)
      const out: Shape[] = [
        rect(x0, y0, w, d, 5, 'base', true),
        rect(x0, d / 2 - back, w, back, 4, 'detail'),
        rect(x0, y0, arm, d, 4, 'detail'),
        rect(w / 2 - arm, y0, arm, d, 4, 'detail'),
      ]
      for (let i = 1; i < n; i++) {
        const x = x0 + arm + (seatW * i) / n
        out.push({
          tag: 'line',
          x1: x,
          y1: y0 + 3,
          x2: x,
          y2: d / 2 - back - 2,
          tone: 'line',
        })
      }
      return out
    }
    case 'bench':
      return [
        rect(x0, y0, w, d, 3, 'base', true),
        {
          tag: 'line',
          x1: x0 + 3,
          y1: y0 + d / 3,
          x2: w / 2 - 3,
          y2: y0 + d / 3,
          tone: 'line',
        },
        {
          tag: 'line',
          x1: x0 + 3,
          y1: y0 + (2 * d) / 3,
          x2: w / 2 - 3,
          y2: y0 + (2 * d) / 3,
          tone: 'line',
        },
      ]
    case 'bed': {
      const head = clamp(d * 0.06, 2.5, 8)
      const pillow = clamp(d * 0.16, 4, 22)
      const n = widthM >= 1.2 ? 2 : 1
      const gap = clamp(w * 0.05, 2, 6)
      const pw = (w - gap * (n + 1)) / n
      const py = d / 2 - head - gap - pillow
      const out: Shape[] = [
        rect(x0, y0, w, d, 5, 'base', true),
        rect(x0, d / 2 - head, w, head, 2, 'detail'),
      ]
      for (let i = 0; i < n; i++)
        out.push(rect(x0 + gap + i * (pw + gap), py, pw, pillow, 4, 'top'))
      const blanket = py - gap - y0
      out.push(rect(x0, y0, w, blanket, 5, 'detail'))
      out.push({
        tag: 'line',
        x1: x0 + 2,
        y1: y0 + blanket * 0.82,
        x2: w / 2 - 2,
        y2: y0 + blanket * 0.82,
        tone: 'line',
      })
      return out
    }
    case 'storage': {
      const front = clamp(d * 0.18, 2, 5)
      const n = clamp(Math.round(widthM / 0.45), 1, 8)
      const out: Shape[] = [
        rect(x0, y0, w, d, 2, 'base', true),
        rect(x0, y0, w, front, 1, 'detail'),
      ]
      for (let i = 1; i < n; i++) {
        const x = x0 + (w * i) / n
        out.push({
          tag: 'line',
          x1: x,
          y1: y0 + front,
          x2: x,
          y2: d / 2,
          tone: 'line',
        })
      }
      return out
    }
    case 'tree': {
      const r = Math.max(w, d) / 2
      return [
        { tag: 'path', d: lobes(0, 0, r, 9), tone: 'leaf', shadow: true },
        {
          tag: 'path',
          d: lobes(-r * 0.14, -r * 0.14, r * 0.52, 7),
          tone: 'leafTop',
        },
        {
          tag: 'ellipse',
          cx: 0,
          cy: 0,
          rx: Math.max(r * 0.12, 1.5),
          ry: Math.max(r * 0.12, 1.5),
          tone: 'trunk',
        },
      ]
    }
    case 'plant': {
      const r = Math.max(w, d) / 2
      return [
        { tag: 'path', d: leaves(r, 6), tone: 'leaf', shadow: true },
        {
          tag: 'ellipse',
          cx: 0,
          cy: 0,
          rx: Math.max(r * 0.18, 1.5),
          ry: Math.max(r * 0.18, 1.5),
          tone: 'leafTop',
        },
      ]
    }
    default:
      return [rect(x0, y0, w, d, 4, 'base', true)]
  }
}

/** A hand-placed fixture (top-left corner, no facing) as a landmark: the long
 * side runs across, and the front faces the middle of the map. */
export function fixtureLandmark(
  f: { x: number; z: number; width: number; depth: number },
  b: { minX: number; maxX: number; minZ: number; maxZ: number },
) {
  const x = f.x + f.width / 2
  const z = f.z + f.depth / 2
  if (f.width >= f.depth) {
    const yawDeg = z < (b.minZ + b.maxZ) / 2 ? 180 : 0
    return { x, z, width: f.width, depth: f.depth, yawDeg }
  }
  const yawDeg = x < (b.minX + b.maxX) / 2 ? 90 : 270
  return { x, z, width: f.depth, depth: f.width, yawDeg }
}
