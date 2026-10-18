import { useEffect, useRef, useState } from 'react'
import type { Sound } from './schema'
import { RIPPLE_MS, audible } from './sound'
import type { Caption, Hearing } from './sound'
import { ListenIn } from './listen'

// What the wearer hears, for every view: the store folds the phone's dashboard.sound reports; these hooks keep a
// view current with them and let this computer listen in. Components that draw it are in components/Hearing.tsx.

type Subscribe = (listener: (sound: Sound) => void) => () => void

export type Heard = ReturnType<typeof audible> & {
  hearing: Hearing
  now: number
}

/** What is audible now, re-read on every sound and ticked while a caption can still end or a source go stale. */
export function useHearing(
  subscribe: Subscribe,
  getHearing: () => Hearing,
): Heard {
  const [hearing, setHearing] = useState<Hearing>(getHearing)
  const [now, setNow] = useState(() => Date.now())
  useEffect(
    () =>
      subscribe(() => {
        setHearing(getHearing())
        setNow(Date.now())
      }),
    [subscribe, getHearing],
  )
  const busy = now - hearing.lastAt < 6000
  useEffect(() => {
    if (!busy) return
    const timer = setInterval(() => setNow(Date.now()), 100)
    return () => clearInterval(timer)
  }, [busy])
  return { ...audible(hearing, now), hearing, now }
}

/** Listen in: this computer plays what the wearer hears, from the same directions. Off until asked. */
export function useListenIn(subscribe: Subscribe) {
  const listen = useRef<ListenIn | null>(null)
  const [on, setOn] = useState(false)
  useEffect(
    () => subscribe((sound) => listen.current?.play(sound)),
    [subscribe],
  )
  useEffect(() => () => listen.current?.close(), [])
  const toggle = () => {
    if (listen.current) {
      listen.current.close()
      listen.current = null
      setOn(false)
    } else {
      listen.current = new ListenIn()
      setOn(true)
    }
  }
  return { on, toggle }
}

/** The ripples still running. */
export function ripples(heard: Heard) {
  return heard.hearing.ripples.filter((r) => heard.now - r.at < RIPPLE_MS)
}

/**
 * The line to show. The phone's own words while they play. Otherwise the snapshot's line if it is a different one,
 * which this browser didn't hear start (opened mid-sentence, a reconnect); its direction is unknown, so none is
 * claimed. Otherwise the line just finished, dimmed, for a few seconds.
 */
export function captionOf(
  heard: Heard,
  spokenInstruction: string | null,
): Caption | null {
  if (heard.caption && heard.speaking) return heard.caption
  if (spokenInstruction && heard.hearing.caption?.text !== spokenInstruction)
    return {
      text: spokenInstruction,
      cue: 'say',
      anchor: 'item',
      from: null,
      at: heard.now,
      until: heard.now,
    }
  return heard.caption
}

/** What is playing in the AirPods right now, in a few words. */
export function playing(heard: Heard, caption: Caption | null) {
  if (heard.speaking)
    return caption?.cue === 'label' ? 'voice label' : 'Marco’s voice'
  if (heard.tone) return 'steady tone'
  if (heard.beacon) return heard.beacon.muffled ? 'beacon, muffled' : 'beacon'
  return null
}

/** Whether the ears are lit: just after a sound, or while Marco speaks. */
export function earsLit(heard: Heard) {
  return heard.now - heard.hearing.ears.at < 700 || heard.speaking
}
