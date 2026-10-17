import { describe, expect, it } from 'vitest'
import example from '../../docs/dashboard.snapshot.example.json'
import { demoSnapshot } from '../data/demo'
import { snapshotSchema } from './schema'
import { ago, direction, guidanceIssue, locationIsValid } from './format'

describe('shared snapshot contract', () => {
  it('parses the backend handoff fixture and the interactive demo', () => {
    expect(snapshotSchema.safeParse(example).success).toBe(true)
    expect(snapshotSchema.safeParse(demoSnapshot()).success).toBe(true)
  })
  it('supports a room without map, camera, sightings or labels', () => {
    const value = demoSnapshot()
    value.data.map = null
    value.data.camera = null
    value.data.wearer = null
    value.data.items[0].lastSeen = null
    expect(snapshotSchema.safeParse(value).success).toBe(true)
  })
  it('rejects malformed positions, invalid bounds and unsupported versions', () => {
    const value = demoSnapshot()
    expect(
      snapshotSchema.safeParse({ ...value, schemaVersion: 2 }).success,
    ).toBe(false)
    value.data.map!.bounds.maxX = value.data.map!.bounds.minX
    expect(snapshotSchema.safeParse(value).success).toBe(false)
    value.data.map = null
    value.data.wearer!.position.x = Infinity
    expect(snapshotSchema.safeParse(value).success).toBe(false)
  })
})

describe('guidance validity', () => {
  it('keeps the coordinate system consistent and hides cues after relocalization', () => {
    const { data } = demoSnapshot()
    expect(locationIsValid(data, data.items[0])).toBe(true)
    data.wearer!.worldMapId = 'different-map'
    expect(locationIsValid(data, data.items[0])).toBe(false)
    expect(guidanceIssue(data, true, data.items[0])).toBe(
      'Location unavailable',
    )
  })
  it('does not show active cues for lost connection, lost phone, tracking or stale pose', () => {
    const { data } = demoSnapshot()
    expect(guidanceIssue(data, false, data.items[0])).toBe('Connection lost')
    data.devices.phone.state = 'disconnected'
    expect(guidanceIssue(data, true, data.items[0])).toBe('iPhone disconnected')
    data.devices.phone.state = 'connected'
    data.devices.phone.tracking = 'relocalizing'
    expect(guidanceIssue(data, true, data.items[0])).toBe('Restoring position')
    data.devices.phone.tracking = 'normal'
    data.wearer!.at = new Date(Date.now() - 6000).toISOString()
    expect(guidanceIssue(data, true, data.items[0])).toBe(
      'Waiting for position',
    )
  })
  it.each([
    [0, 'Ahead of you'],
    [90, 'To your right'],
    [-90, 'To your left'],
    [145, 'Behind you, to your right'],
    [180, 'Behind you'],
    [360, 'Ahead of you'],
  ])('formats bearing %s', (bearing, text) => {
    expect(direction(Number(bearing))).toBe(text)
  })
  it('formats future observations without negative ages', () => {
    expect(
      ago('2026-10-17T22:00:01Z', Date.parse('2026-10-17T22:00:00Z')),
    ).toBe('Just now')
    expect(
      ago('2026-10-17T21:00:00Z', Date.parse('2026-10-17T22:00:00Z')),
    ).toBe('1 hour ago')
  })
})
