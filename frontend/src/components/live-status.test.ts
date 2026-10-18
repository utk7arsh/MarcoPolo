import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { demoSnapshot } from '../data/demo'
import type { DashboardData } from '../lib/schema'
import { audible, initialHearing } from '../lib/sound'
import { Live } from './Live'
import { MapView } from './MapView'
import { CameraView } from './CameraView'

const now = Date.parse('2026-10-17T22:00:00Z')
function renderLive(data: DashboardData, online = true) {
  return renderToStaticMarkup(
    createElement(Live, {
      now,
      data,
      online,
      pending: false,
      pendingTarget: null,
      onStop() {},
      onObjects() {},
      demo: false,
      heard: { ...audible(initialHearing, now), hearing: initialHearing, now },
      listen: { on: false, onToggle() {} },
    }),
  )
}
const unavailable: [string, (data: DashboardData) => void][] = [
  [
    'reset session map',
    (data) => {
      data.session.worldMapId = 'new-map'
    },
  ],
  [
    'reset wearer map',
    (data) => {
      data.wearer!.worldMapId = 'new-map'
    },
  ],
  [
    'different displayed map',
    (data) => {
      data.map!.worldMapId = 'old-map'
    },
  ],
  [
    'unknown session map',
    (data) => {
      data.session.worldMapId = null
    },
  ],
  [
    'missing map',
    (data) => {
      data.map = null
    },
  ],
  [
    'missing wearer',
    (data) => {
      data.wearer = null
    },
  ],
  [
    'stale pose',
    (data) => {
      data.wearer!.at = new Date(now - 6000).toISOString()
    },
  ],
  [
    'stale phone',
    (data) => {
      data.devices.phone.lastMessageAt = new Date(now - 6000).toISOString()
    },
  ],
  [
    'disconnected phone',
    (data) => {
      data.devices.phone.state = 'disconnected'
    },
  ],
  [
    'lost tracking',
    (data) => {
      data.devices.phone.tracking = 'limited'
    },
  ],
]

describe('live map identity and freshness', () => {
  it('shows a current position and target line only for a consistent, fresh map', () => {
    const html = renderLive(demoSnapshot(now).data)
    expect(html).toContain('Live position')
    expect(html).toContain('current position')
    expect(html).toContain('>You</text>')
    expect(html).toContain('stroke-dasharray="4 7"')
    expect(
      html.match(/<button[^>]*class="text-button"[^>]*>/)?.[0],
    ).not.toContain('disabled')
  })
  it.each(unavailable)(
    'suppresses live position and recenter for %s',
    (_, change) => {
      const { data } = demoSnapshot(now)
      change(data)
      const html = renderLive(data)
      expect(html).toContain('Position unavailable')
      expect(html).not.toContain('Live position')
      expect(html).not.toContain('current position')
      expect(html).not.toContain('>You</text>')
      expect(html).not.toContain('stroke-dasharray="4 7"')
      expect(html).toContain('Coffee table')
      if (data.map)
        expect(
          html.match(/<button[^>]*class="text-button"[^>]*>/)?.[0],
        ).toContain('disabled')
    },
  )
  it('hides current position while offline without losing remembered items', () => {
    const html = renderLive(demoSnapshot(now).data, false)
    expect(html).not.toContain('Live position')
    expect(html).not.toContain('>You</text>')
    expect(html).toContain('Coffee table')
  })
  it.each(unavailable.slice(0, 4))(
    'MapView itself rejects %s even if its caller says live',
    (_, change) => {
      const { data } = demoSnapshot(now)
      change(data)
      const html = renderToStaticMarkup(
        createElement(MapView, { data, live: true, targetId: 'keys' }),
      )
      expect(html).not.toContain('current position')
      expect(html).not.toContain('>You</text>')
      expect(html).not.toContain('stroke-dasharray="4 7"')
      expect(
        html.match(/<button[^>]*class="text-button"[^>]*>/)?.[0],
      ).toContain('disabled')
    },
  )
})

describe('camera empty state', () => {
  it('waits for a missing camera instead of reporting a failed frame', () => {
    const { data } = demoSnapshot(now)
    data.camera = null
    const html = renderToStaticMarkup(
      createElement(CameraView, {
        data,
        now,
        online: true,
        demo: false,
        targetId: null,
      }),
    )
    expect(html).toContain('Waiting for camera')
    expect(html).not.toContain('Frame unavailable')
  })
  it('reports disconnection before missing camera state', () => {
    const { data } = demoSnapshot(now)
    data.camera = null
    const html = renderToStaticMarkup(
      createElement(CameraView, {
        data,
        now,
        online: false,
        demo: false,
        targetId: null,
      }),
    )
    expect(html).toContain('Camera disconnected')
    expect(html).not.toContain('Frame unavailable')
  })
})
