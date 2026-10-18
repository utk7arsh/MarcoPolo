import type { Command, Snapshot, Sound } from '../lib/schema'
import type { Transport } from '../lib/transport'
import { guidingLoop, walkthrough } from './soundScript'
import type { Step } from './soundScript'

export const scenarios = [
  ['guiding', 'Finding keys'],
  ['walkthrough', 'Finding keys, start to finish'],
  ['near', 'Within reach'],
  ['found', 'Object found'],
  ['moved', 'Keys moved'],
  ['photon', 'Photon label saved'],
  ['offline', 'iPhone disconnected'],
  ['tracking', 'Restoring position'],
  ['no-map', 'Map unavailable'],
  ['empty', 'No objects'],
] as const
export type Scenario = (typeof scenarios)[number][0]

export function demoSnapshot(now = Date.now()): Snapshot {
  now = Math.floor(now / 1000) * 1000
  const time = (minutes = 0) => new Date(now - minutes * 60000).toISOString()
  const sighting = (
    surface: string,
    minutes: number,
    x: number,
    z: number,
  ) => ({
    at: time(minutes),
    roomId: 'living-room',
    roomName: 'Living room',
    surface,
    worldMapId: 'living-room-1',
    position: { x, y: 0.75, z },
  })
  const label = {
    audioUrl: '/audio/keys.wav',
    transcript: 'Your house keys.',
    authorName: null,
    durationSeconds: null,
    createdAt: time(30),
  }
  return {
    type: 'dashboard.snapshot',
    schemaVersion: 1,
    streamId: 'demo',
    sequence: 1,
    sentAt: time(),
    data: {
      session: {
        id: 'demo-session',
        deviceId: 'demo-iphone',
        roomId: 'living-room',
        roomName: 'Living room',
        worldMapId: 'living-room-1',
      },
      devices: {
        phone: {
          state: 'connected',
          tracking: 'normal',
          lastMessageAt: time(),
        },
        airpods: { state: 'connected', lastMessageAt: time() },
      },
      map: {
        worldMapId: 'living-room-1',
        bounds: { minX: -2, maxX: 3, minZ: -2, maxZ: 2 },
        walls: [
          { from: { x: -2, z: -2 }, to: { x: 3, z: -2 } },
          { from: { x: 3, z: -2 }, to: { x: 3, z: 2 } },
          { from: { x: 3, z: 2 }, to: { x: 1.45, z: 2 } },
          { from: { x: 0.6, z: 2 }, to: { x: -2, z: 2 } },
          { from: { x: -2, z: 2 }, to: { x: -2, z: -2 } },
        ],
        fixtures: [
          {
            id: 'sofa',
            name: 'Sofa',
            kind: 'sofa',
            x: -1.7,
            z: -1.55,
            width: 0.85,
            depth: 2.75,
          },
          {
            id: 'coffee-table',
            name: 'Coffee table',
            kind: 'table',
            x: -0.05,
            z: 0.65,
            width: 1.7,
            depth: 1.15,
          },
          {
            id: 'console',
            name: 'Console table',
            kind: 'storage',
            x: 2.2,
            z: -1.35,
            width: 0.5,
            depth: 2.2,
          },
        ],
      },
      wearer: {
        at: time(),
        worldMapId: 'living-room-1',
        position: { x: 0, y: 1.25, z: -0.4 },
        bodyYawDeg: 0,
        headYawDeg: 0,
      },
      items: [
        {
          id: 'keys',
          name: 'Keys',
          photoUrl: '/images/keys.jpg',
          voiceLabel: label,
          lastSeen: sighting('Coffee table', 2, 1.2, 1.3),
        },
        {
          id: 'mug',
          name: 'Blue mug',
          photoUrl: null,
          voiceLabel: null,
          lastSeen: sighting('Sofa arm', 8, -1.3, 0.75),
        },
        {
          id: 'glasses',
          name: 'Reading glasses',
          photoUrl: null,
          voiceLabel: null,
          lastSeen: sighting('Desk', 24, 2.45, -0.9),
        },
        {
          id: 'wallet',
          name: 'Wallet',
          photoUrl: null,
          voiceLabel: null,
          lastSeen: sighting('Console table', 60, 2.45, -0.25),
        },
      ],
      camera: {
        frameId: 1,
        capturedAt: time(),
        widthPx: 1600,
        heightPx: 900,
        imageUrl: '/images/keys.jpg',
        boxes: [{ itemId: 'keys', boxPx: [375, 120, 1225, 720] }],
      },
      navigation: {
        state: 'guiding',
        targetItemId: 'keys',
        distanceM: 2.1,
        bearingDeg: 145,
        bearingReference: 'head',
        audioPattern: 'beacon',
        spokenInstruction: 'Turn right. Your keys are behind you.',
        updatedAt: time(),
      },
      registrations: [
        {
          id: 'mug-label',
          status: 'waiting_for_label',
          photoUrl: null,
          recipientName: null,
          itemId: 'mug',
          label: null,
          updatedAt: time(),
          message: null,
        },
      ],
      recentMemory: [
        {
          id: 'keys-2',
          itemId: 'keys',
          kind: 'seen',
          at: time(2),
          surface: 'Coffee table',
        },
        {
          id: 'keys-1',
          itemId: 'keys',
          kind: 'seen',
          at: time(38),
          surface: 'Console table',
        },
      ],
      lastCommand: null,
    },
  }
}

export function createDemoTransport(initial: Scenario = 'guiding') {
  let snapshot = demoSnapshot()
  let emit: ((value: Snapshot) => void) | undefined
  let ack: ReturnType<typeof setTimeout> | undefined
  // What the wearer would hear in this scenario (soundScript.ts), played on a 50 ms clock.
  let hear: ((value: Sound) => void) | undefined
  let script: { period: number; steps: Step[] } | null = null
  let loopStart = 0
  let cursor = 0
  let lastPublish = 0
  const play = (next: typeof script) => {
    script = next
    loopStart = Date.now()
    cursor = 0
    if (!next)
      hear?.({
        kind: 'field',
        tDevice: Date.now() / 1000,
        headYawDeg: 0,
        beacon: null,
        voice: null,
      })
  }
  const soundTick = () => {
    if (!script) return
    let elapsed = Date.now() - loopStart
    if (elapsed >= script.period) {
      loopStart += script.period * Math.floor(elapsed / script.period)
      elapsed = Date.now() - loopStart
      cursor = 0
    }
    let moved = false
    while (cursor < script.steps.length && script.steps[cursor].t <= elapsed) {
      const step = script.steps[cursor++]
      hear?.(step.sound)
      if (step.navigation) {
        Object.assign(snapshot.data.navigation, step.navigation)
        moved = true
      }
      const wearer = snapshot.data.wearer
      if (step.wearer && wearer) {
        wearer.position.x = step.wearer.x
        wearer.position.z = step.wearer.z
        wearer.headYawDeg = step.wearer.headYawDeg
        wearer.bodyYawDeg = step.wearer.bodyYawDeg
        moved = true
      }
    }
    if (moved && Date.now() - lastPublish >= 200) publish()
  }
  const scriptFor = (scenario: Scenario) => {
    const keys = snapshot.data.items.find((item) => item.id === 'keys')
    if (scenario === 'guiding') return guidingLoop()
    if (scenario === 'walkthrough')
      return walkthrough(
        keys?.voiceLabel?.transcript ?? null,
        keys?.voiceLabel?.audioUrl ?? null,
        snapshot.data.wearer && keys?.lastSeen?.position
          ? {
              from: snapshot.data.wearer.position,
              keys: keys.lastSeen.position,
            }
          : undefined,
      )
    return null
  }
  const publish = () => {
    const time = new Date().toISOString()
    snapshot.sequence++
    snapshot.sentAt = time
    snapshot.data.devices.phone.lastMessageAt = time
    snapshot.data.devices.airpods.lastMessageAt = time
    snapshot.data.navigation.updatedAt = time
    if (snapshot.data.wearer) snapshot.data.wearer.at = time
    // The fixture represents a still frame, not a simulated live video stream.
    lastPublish = Date.now()
    emit?.(structuredClone(snapshot))
  }
  const setScenario = (scenario: Scenario) => {
    const sequence = snapshot.sequence
    snapshot = demoSnapshot()
    snapshot.sequence = sequence
    const data = snapshot.data
    if (scenario === 'near')
      Object.assign(data.navigation, {
        state: 'within_reach',
        distanceM: 0.24,
        bearingDeg: 0,
        audioPattern: 'steady',
        spokenInstruction: 'Within reach. Reach forward.',
      })
    if (scenario === 'found')
      Object.assign(data.navigation, {
        state: 'found',
        distanceM: null,
        bearingDeg: null,
        audioPattern: 'confirmation',
        spokenInstruction: 'Got it.',
      })
    if (scenario === 'offline') data.devices.phone.state = 'disconnected'
    if (scenario === 'tracking') data.devices.phone.tracking = 'relocalizing'
    if (scenario === 'no-map') data.map = null
    if (scenario === 'empty') {
      data.items = []
      data.registrations = []
      data.recentMemory = []
      data.map = null
      Object.assign(data.navigation, {
        state: 'idle',
        targetItemId: null,
        distanceM: null,
        bearingDeg: null,
        audioPattern: 'off',
        spokenInstruction: null,
      })
    }
    if (scenario === 'moved') {
      Object.assign(data.items[0].lastSeen!, {
        surface: 'Console table',
        at: new Date().toISOString(),
        position: { x: 2.45, y: 0.8, z: -0.25 },
      })
      Object.assign(data.navigation, {
        distanceM: 2.5,
        bearingDeg: 88,
        spokenInstruction: 'Your keys are on the console table, to your right.',
      })
      data.recentMemory.unshift({
        id: 'keys-moved',
        itemId: 'keys',
        kind: 'moved',
        at: new Date().toISOString(),
        surface: 'Console table',
      })
    }
    if (scenario === 'photon') {
      const label = {
        audioUrl: null,
        transcript: 'The blue mug.',
        authorName: null,
        durationSeconds: null,
        createdAt: new Date().toISOString(),
      }
      Object.assign(data.registrations[0], { status: 'saved', label })
      data.items[1].voiceLabel = label
      data.recentMemory.unshift({
        id: 'mug-label-saved',
        itemId: 'mug',
        kind: 'label_saved',
        at: new Date().toISOString(),
        surface: null,
      })
    }
    play(scriptFor(scenario))
    publish()
  }
  const transport: Transport & { setScenario: typeof setScenario } = {
    start(onSnapshot, onConnection, onSound) {
      emit = onSnapshot
      hear = onSound
      setScenario(initial)
      onConnection('live')
      const heartbeat = setInterval(publish, 1000)
      const sounds = setInterval(soundTick, 50)
      return () => {
        clearInterval(heartbeat)
        clearInterval(sounds)
        clearTimeout(ack)
        emit = undefined
        hear = undefined
      }
    },
    async send(command: Command) {
      snapshot.data.lastCommand = {
        commandId: command.commandId,
        status: 'pending',
        reason: null,
      }
      publish()
      ack = setTimeout(() => {
        snapshot.data.lastCommand = {
          commandId: command.commandId,
          status: 'accepted',
          reason: null,
        }
        play(command.type === 'stop' ? null : scriptFor('walkthrough'))
        if (command.type === 'stop') {
          Object.assign(snapshot.data.navigation, {
            state: 'idle',
            targetItemId: null,
            distanceM: null,
            bearingDeg: null,
            audioPattern: 'off',
            spokenInstruction: null,
          })
        } else {
          const item = snapshot.data.items.find(
            (item) => item.id === command.itemId,
          )
          const valid = !!item?.lastSeen?.position
          Object.assign(snapshot.data.navigation, {
            state: valid ? 'guiding' : 'unavailable',
            targetItemId: command.itemId,
            distanceM: valid ? 2.1 : null,
            bearingDeg: valid ? 145 : null,
            audioPattern: valid ? 'beacon' : 'off',
            spokenInstruction: valid
              ? `Turn right. Your ${item.name.toLowerCase()} ${item.name === 'Keys' || item.name === 'Reading glasses' ? 'are' : 'is'} behind you.`
              : null,
          })
        }
        publish()
      }, 650)
    },
    setScenario,
  }
  return transport
}
