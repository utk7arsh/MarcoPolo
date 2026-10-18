import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { demoSnapshot } from '../data/demo'
import type { Sound, SoundCue } from '../lib/schema'
import { audible, hear, initialHearing } from '../lib/sound'
import type { Hearing } from '../lib/sound'
import { captionOf, playing } from '../lib/hearing'
import type { Heard } from '../lib/hearing'
import { ListeningHead, SoundCaption, SoundPill } from './Hearing'
import { Live } from './Live'
import { MapView } from './MapView'

const now = Date.now()
const heardOf = (hearing: Hearing, at = now): Heard => ({
  ...audible(hearing, at),
  hearing,
  now: at,
})
const cue = (name: SoundCue['cue'], extra: Partial<SoundCue> = {}): Sound => ({
  kind: 'cue',
  tDevice: 1,
  cue: name,
  source: ['say', 'label', 'blip'].includes(name) ? 'voice' : 'beacon',
  anchor: 'item',
  azimuthDeg: 145,
  elevationDeg: -20,
  distanceM: 2.2,
  muffled: name === 'beep' ? true : null,
  text: null,
  durationS: null,
  audioUrl: null,
  ...extra,
})
const field: Sound = {
  kind: 'field',
  tDevice: 1,
  headYawDeg: 0,
  beacon: { azimuthDeg: 145, elevationDeg: -20, distanceM: 2.2, muffled: true },
  voice: null,
}
const beeping = heardOf(
  hear(hear(initialHearing, field, now), cue('beep'), now),
)
const speaking = heardOf(
  hear(
    initialHearing,
    cue('say', {
      text: 'Polo! Behind you, two steps, on the table.',
      durationS: 3,
    }),
    now,
  ),
)

describe('what the wearer hears, in every view', () => {
  it('the guidance panel’s head points at the sound, muffled behind the head', () => {
    const html = renderToStaticMarkup(
      createElement(ListeningHead, { heard: beeping, bearingDeg: 30 }),
    )
    expect(html).toContain('Sound at 145 degrees from where the wearer faces')
    expect(html).toContain('sound-beacon muffled')
    expect(html).toContain('sound-ripple muffled')
    expect(html).toContain('sound-ear flash')
  })
  it('falls back to the snapshot’s bearing when no sound arrives', () => {
    const html = renderToStaticMarkup(
      createElement(ListeningHead, {
        heard: heardOf(initialHearing),
        bearingDeg: -60,
      }),
    )
    expect(html).toContain('Sound at -60 degrees')
  })
  it('says what is playing, and shows the phone’s words with where they came from', () => {
    expect(playing(beeping, null)).toBe('beacon, muffled')
    const caption = captionOf(speaking, null)
    expect(playing(speaking, caption)).toBe('Marco’s voice')
    const html = renderToStaticMarkup(
      createElement(SoundCaption, { caption, speaking: true }),
    )
    expect(html).toContain('Polo! Behind you, two steps, on the table.')
    expect(html).toContain('Marco, from behind, on the right')
  })
  it('uses the snapshot’s line only for a line it missed, never to repeat one, and claims no direction for it', () => {
    const missed = captionOf(beeping, 'Turn right.')
    expect(missed?.text).toBe('Turn right.')
    expect(
      renderToStaticMarkup(
        createElement(SoundCaption, { caption: missed, speaking: false }),
      ),
    ).toContain('<figcaption>Marco</figcaption>')
    const later = heardOf(speaking.hearing, now + 60000)
    expect(
      captionOf(later, 'Polo! Behind you, two steps, on the table.'),
    ).toBeNull()
  })
  it('the room map gives the wearer a head that turns, ears, and the sound’s clock hour', () => {
    const data = demoSnapshot(now).data
    const html = renderToStaticMarkup(
      createElement(MapView, {
        data,
        live: true,
        targetId: 'keys',
        heard: beeping,
      }),
    )
    expect(html).toContain('map-head sounding')
    expect(html).toContain('sound-ear')
    expect(html).toContain('>5</text>')
    expect(html).toMatch(/sound-ripple\s+muffled/)
    expect(
      renderToStaticMarkup(
        createElement(MapView, { data, live: true, targetId: 'keys' }),
      ),
    ).not.toContain('map-head')
  })
  it('the Live panel says what is playing and offers listen in as an opt-in', () => {
    const data = demoSnapshot(now).data
    const html = renderToStaticMarkup(
      createElement(Live, {
        now,
        data,
        online: true,
        pending: false,
        pendingTarget: null,
        onStop() {},
        onObjects() {},
        demo: false,
        heard: beeping,
        listen: { on: false, onToggle() {} },
      }),
    )
    expect(html).toContain('Playing in AirPods: beacon, muffled')
    expect(html).toContain('aria-pressed="false"')
    expect(html).toContain('Listen in')
    expect(html).not.toContain('>Sound<')
  })
  it('away from Live, a pill shows the line in the AirPods, and nothing when quiet', () => {
    expect(
      renderToStaticMarkup(createElement(SoundPill, { heard: speaking })),
    ).toContain(
      'In the AirPods</span> “Polo! Behind you, two steps, on the table.”',
    )
    expect(
      renderToStaticMarkup(
        createElement(SoundPill, { heard: heardOf(initialHearing) }),
      ),
    ).toBe('')
  })
})
