import { landmarkShapes, TONES, type Shape } from '../lib/roomShapes'

function draw(s: Shape, i: number, shadow?: string) {
  const tone = TONES[s.tone]
  const paint = shadow
    ? { fill: shadow, stroke: 'none' }
    : { fill: tone.fill, stroke: tone.stroke, strokeWidth: 1 }
  switch (s.tag) {
    case 'rect':
      return (
        <rect
          key={i}
          x={s.x}
          y={s.y}
          width={s.w}
          height={s.h}
          rx={s.r}
          {...paint}
        />
      )
    case 'ellipse':
      return (
        <ellipse key={i} cx={s.cx} cy={s.cy} rx={s.rx} ry={s.ry} {...paint} />
      )
    case 'path':
      return <path key={i} d={s.d} {...paint} />
    case 'line':
      return (
        <line
          key={i}
          x1={s.x1}
          y1={s.y1}
          x2={s.x2}
          y2={s.y2}
          stroke={tone.stroke}
          strokeWidth="1"
          strokeLinecap="round"
        />
      )
  }
}

/** One landmark's stock shape at (x, y) in map pixels, turned to yawDeg, with a
 * soft shadow that always falls the same way. */
export function RoomShape({
  kind,
  x,
  y,
  width,
  depth,
  yawDeg,
  scale,
  round,
  label,
}: {
  kind: string
  x: number
  y: number
  width: number
  depth: number
  yawDeg: number
  scale: number
  round?: boolean
  label: string
}) {
  const shapes = landmarkShapes(kind, width, depth, scale, round)
  return (
    <g className={`room-shape room-shape-${kind}`}>
      <title>{label}</title>
      <g
        transform={`translate(${x + 1.5} ${y + 2.5}) rotate(${yawDeg})`}
        opacity="0.08"
      >
        {shapes
          .filter((s) => s.tag !== 'line' && s.shadow)
          .map((s, i) => draw(s, i, '#1f2933'))}
      </g>
      <g transform={`translate(${x} ${y}) rotate(${yawDeg})`}>
        {shapes.map((s, i) => draw(s, i))}
      </g>
    </g>
  )
}
