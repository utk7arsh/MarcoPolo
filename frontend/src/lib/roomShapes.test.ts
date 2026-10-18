import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { MapView } from '../components/MapView'
import { demoSnapshot } from '../data/demo'
import {
  fixtureLandmark,
  landmarkShapes,
  lobes,
  type Shape,
} from './roomShapes'
import { snapshotSchema } from './schema'

const KINDS = [
  'table',
  'chair',
  'sofa',
  'bench',
  'bed',
  'storage',
  'tree',
  'plant',
]

function numbers(s: Shape) {
  return Object.values(s).filter((v) => typeof v === 'number') as number[]
}

describe('room map reference shapes', () => {
  it('gives every kind a finite shape that casts a shadow', () => {
    for (const kind of KINDS) {
      const shapes = landmarkShapes(kind, 1.2, 0.8, 60)
      expect(shapes.length).toBeGreaterThan(0)
      expect(shapes[0]).toMatchObject({ shadow: true })
      for (const s of shapes)
        expect(numbers(s).every((v) => Number.isFinite(v))).toBe(true)
    }
    expect(landmarkShapes('something-new', 1, 1, 60)).toHaveLength(1)
  })
  it('draws a round table as an ellipse and a square one as a rectangle', () => {
    expect(landmarkShapes('table', 1, 1, 60, true)[0].tag).toBe('ellipse')
    expect(landmarkShapes('table', 1, 1, 60)[0].tag).toBe('rect')
  })
  it("puts a chair's back behind the sitter (the front faces up)", () => {
    const [, back] = landmarkShapes('chair', 0.5, 0.5, 60)
    expect(back.tag).toBe('rect')
    if (back.tag === 'rect') expect(back.y).toBeGreaterThan(0)
  })
  it('adds sofa cushions with width and a second pillow on a double bed', () => {
    const lines = (kind: string, w: number) =>
      landmarkShapes(kind, w, 0.9, 60).filter((s) => s.tag === 'line').length
    expect(lines('sofa', 2.4)).toBeGreaterThan(lines('sofa', 1.0))
    const pillows = (w: number) =>
      landmarkShapes('bed', w, 2, 60).filter((s) => s.tone === 'top').length
    expect(pillows(1.6)).toBe(2)
    expect(pillows(0.9)).toBe(1)
  })
  it('closes the canopy outline', () => {
    const d = lobes(0, 0, 10, 9)
    expect(d.startsWith('M')).toBe(true)
    expect(d.endsWith('Z')).toBe(true)
    expect(d.match(/Q/g)).toHaveLength(9)
  })
  it('turns a hand-placed fixture to face the middle of the map', () => {
    const b = { minX: -2, maxX: 3, minZ: -2, maxZ: 2 }
    const sofa = { x: -1.7, z: -1.55, width: 0.85, depth: 2.75 }
    expect(fixtureLandmark(sofa, b)).toMatchObject({
      width: 2.75,
      depth: 0.85,
      yawDeg: 90,
    })
    const shelf = { x: 2.2, z: -1.35, width: 0.5, depth: 2.2 }
    expect(fixtureLandmark(shelf, b).yawDeg).toBe(270)
    const table = { x: -0.05, z: 0.65, width: 1.7, depth: 1.15 }
    expect(fixtureLandmark(table, b)).toMatchObject({ x: 0.8, yawDeg: 0 })
  })
})

describe('scanned landmarks in the snapshot and on the map', () => {
  const marks = [
    {
      id: 'table-1',
      kind: 'table',
      x: 0.5,
      z: 0,
      width: 1.2,
      depth: 0.8,
      yawDeg: 90,
      shape: 'round',
    },
    {
      id: 'chair-1',
      kind: 'chair',
      x: 1.2,
      z: 0,
      width: 0.5,
      depth: 0.5,
      yawDeg: 270,
    },
    {
      id: 'thing-1',
      kind: 'fridge',
      x: 2,
      z: 1,
      width: 0.7,
      depth: 0.7,
      yawDeg: 0,
    },
  ]
  it('parses landmarks, including kinds this dashboard does not know yet', () => {
    const value = demoSnapshot()
    value.data.map!.landmarks = marks
    expect(snapshotSchema.safeParse(value).success).toBe(true)
    value.data.map!.landmarks = [{ ...marks[0], width: 0 }]
    expect(snapshotSchema.safeParse(value).success).toBe(false)
  })
  it('draws each landmark with its shape and a label, and says the room was scanned', () => {
    const { data } = demoSnapshot()
    const before = renderToStaticMarkup(
      createElement(MapView, { data, live: true, targetId: null }),
    )
    expect(before).not.toContain('Scanned room')
    data.map!.landmarks = marks
    const html = renderToStaticMarkup(
      createElement(MapView, { data, live: true, targetId: null }),
    )
    expect(html).toContain('room-shape-chair')
    expect(html).toContain('<title>Chair (scanned)</title>')
    expect(html).toContain('<title>Object (scanned)</title>')
    expect(html).toContain('<ellipse')
    expect(html).toContain('Scanned room')
    expect(html).toContain('Coffee table')
  })
})
