// POC 27: what the dashboard map will look like for a recorded session, using the dashboard's own shape code
// (frontend/src/lib/roomShapes.ts) and MapView's scale, colours and wall style. Node 24 runs it as is:
//   node poc/pocs/poc27_room_map/preview.ts /tmp/poc27/<session>.layout.json out.svg [title]
// The layout JSON comes from run.py (walls, objects, cams). This is a picture for review, not a test.
import { readFileSync, writeFileSync } from 'node:fs'
import {
  landmarkShapes,
  LANDMARK_LABELS,
  TONES,
  type Shape,
} from '../../../frontend/src/lib/roomShapes.ts'

type Obj = {
  kind: string
  x: number
  z: number
  width: number
  depth: number
  yaw: number
  shape?: string
}
const [src, out, title = ''] = process.argv.slice(2)
const lay = JSON.parse(readFileSync(src, 'utf8')) as {
  walls: [[number, number], [number, number]][]
  objects: Obj[]
  cams: [number, number][]
}
const xs = [
  ...lay.walls.flatMap((w) => [w[0][0], w[1][0]]),
  ...lay.objects.flatMap((o) => [o.x - o.width / 2, o.x + o.width / 2]),
  ...lay.cams.map((c) => c[0]),
]
const zs = [
  ...lay.walls.flatMap((w) => [w[0][1], w[1][1]]),
  ...lay.objects.flatMap((o) => [o.z - o.depth / 2, o.z + o.depth / 2]),
  ...lay.cams.map((c) => c[1]),
]
const b = {
  minX: Math.min(...xs) - 0.5,
  maxX: Math.max(...xs) + 0.5,
  minZ: Math.min(...zs) - 0.5,
  maxZ: Math.max(...zs) + 0.5,
}
const width = b.maxX - b.minX
const depth = b.maxZ - b.minZ
const scale = Math.min(650 / width, 440 / depth)
const X = (v: number) => 400 + (v - (b.minX + b.maxX) / 2) * scale
const Z = (v: number) => 260 + (v - (b.minZ + b.maxZ) / 2) * scale
const f = (v: number) => Math.round(v * 10) / 10

function draw(s: Shape, shadow?: string): string {
  const t = TONES[s.tone]
  const paint = shadow
    ? `fill="${shadow}" stroke="none"`
    : `fill="${t.fill}" stroke="${t.stroke}" stroke-width="1"`
  switch (s.tag) {
    case 'rect':
      return `<rect x="${f(s.x)}" y="${f(s.y)}" width="${f(s.w)}" height="${f(s.h)}" rx="${f(s.r)}" ${paint}/>`
    case 'ellipse':
      return `<ellipse cx="${f(s.cx)}" cy="${f(s.cy)}" rx="${f(s.rx)}" ry="${f(s.ry)}" ${paint}/>`
    case 'path':
      return `<path d="${s.d}" ${paint}/>`
    case 'line':
      return `<line x1="${f(s.x1)}" y1="${f(s.y1)}" x2="${f(s.x2)}" y2="${f(s.y2)}" stroke="${t.stroke}" stroke-width="1" stroke-linecap="round"/>`
  }
}

const parts: string[] = []
const vb = [X(b.minX) - 40, Z(b.minZ) - 35, width * scale + 80, depth * scale + 90]
parts.push(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb.map(f).join(' ')}" width="${f(vb[2] * 1.5)}" height="${f(vb[3] * 1.5)}" font-family="Helvetica, Arial, sans-serif">`,
  `<rect x="${f(vb[0])}" y="${f(vb[1])}" width="${f(vb[2])}" height="${f(vb[3])}" fill="#ffffff"/>`,
  `<rect x="${f(X(b.minX))}" y="${f(Z(b.minZ))}" width="${f(width * scale)}" height="${f(depth * scale)}" fill="#fafafa"/>`,
)
for (const [a, c] of lay.walls)
  parts.push(
    `<line x1="${f(X(a[0]))}" y1="${f(Z(a[1]))}" x2="${f(X(c[0]))}" y2="${f(Z(c[1]))}" stroke="#b9bec6" stroke-width="5" stroke-linecap="round"/>`,
  )
parts.push(
  `<text x="${f(X(b.minX) + 25)}" y="${f(Z(b.minZ) + 31)}" font-size="12" letter-spacing="1.7" fill="#62666d">${title.toUpperCase()}</text>`,
)
for (const o of lay.objects) {
  const shapes = landmarkShapes(o.kind, o.width, o.depth, scale, o.shape === 'round')
  const shadow = shapes.filter((s) => s.tag !== 'line' && s.shadow)
  parts.push(
    `<g><title>${LANDMARK_LABELS[o.kind] ?? 'Object'}</title>`,
    `<g transform="translate(${f(X(o.x) + 1.5)} ${f(Z(o.z) + 2.5)}) rotate(${o.yaw})" opacity="0.08">${shadow.map((s) => draw(s, '#1f2933')).join('')}</g>`,
    `<g transform="translate(${f(X(o.x))} ${f(Z(o.z))}) rotate(${o.yaw})">${shapes.map((s) => draw(s)).join('')}</g></g>`,
  )
}
if (lay.cams.length) {
  const d = lay.cams
    .map((c, i) => `${i ? 'L' : 'M'}${f(X(c[0]))} ${f(Z(c[1]))}`)
    .join('')
  parts.push(
    `<path d="${d}" fill="none" stroke="#9cb8d8" stroke-width="1.5" stroke-dasharray="4 7"/>`,
  )
  const [lx, lz] = lay.cams[lay.cams.length - 1]
  parts.push(
    `<g transform="translate(${f(X(lx))} ${f(Z(lz))})"><circle r="18" fill="#1559d6" opacity=".08"/><circle r="10" fill="#1559d6" stroke="white" stroke-width="4"/></g>`,
  )
}
parts.push('</svg>')
writeFileSync(out, parts.join('\n'))
console.log(`wrote ${out}: ${lay.walls.length} walls, ${lay.objects.length} objects`)
