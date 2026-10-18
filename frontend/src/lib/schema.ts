import { z } from 'zod'

const timestamp = z.iso.datetime()
const coordinate = z.number().finite()
const point = z.object({ x: coordinate, y: coordinate, z: coordinate })
const flatPoint = z.object({ x: coordinate, z: coordinate })
const connection = z.enum(['connected', 'disconnected', 'unknown'])
const voiceLabel = z.object({
  audioUrl: z.string().nullable(),
  transcript: z.string().nullable(),
  authorName: z.string().nullable(),
  durationSeconds: z.number().nonnegative().nullable(),
  createdAt: timestamp,
})
const lastSeen = z.object({
  at: timestamp,
  roomId: z.string(),
  roomName: z.string(),
  surface: z.string().nullable(),
  worldMapId: z.string().nullable(),
  position: point.nullable(),
})
export const itemSchema = z.object({
  id: z.string(),
  name: z.string(),
  photoUrl: z.string().nullable(),
  voiceLabel: voiceLabel.nullable(),
  lastSeen: lastSeen.nullable(),
})
export const snapshotSchema = z.object({
  type: z.literal('dashboard.snapshot'),
  schemaVersion: z.literal(1),
  streamId: z.string(),
  sequence: z.number().int().nonnegative(),
  sentAt: timestamp,
  data: z.object({
    session: z.object({
      id: z.string(),
      deviceId: z.string(),
      roomId: z.string(),
      roomName: z.string(),
      worldMapId: z.string().nullable(),
    }),
    devices: z.object({
      phone: z.object({
        state: connection,
        lastMessageAt: timestamp.nullable(),
        tracking: z.enum(['normal', 'limited', 'relocalizing', 'unavailable']),
      }),
      airpods: z.object({
        state: connection,
        lastMessageAt: timestamp.nullable(),
      }),
    }),
    map: z
      .object({
        worldMapId: z.string(),
        bounds: z
          .object({
            minX: coordinate,
            maxX: coordinate,
            minZ: coordinate,
            maxZ: coordinate,
          })
          .refine(
            (b) => b.maxX > b.minX && b.maxZ > b.minZ,
            'Map bounds must have positive area',
          ),
        walls: z.array(z.object({ from: flatPoint, to: flatPoint })).nullable(),
        fixtures: z
          .array(
            z.object({
              id: z.string(),
              name: z.string(),
              kind: z.enum(['table', 'sofa', 'storage']),
              x: coordinate,
              z: coordinate,
              width: z.number().positive(),
              depth: z.number().positive(),
            }),
          )
          .optional(),
        landmarks: z
          .array(
            z.object({
              id: z.string(),
              kind: z.string(),
              x: coordinate,
              z: coordinate,
              width: z.number().positive(),
              depth: z.number().positive(),
              yawDeg: coordinate,
              shape: z.string().optional(),
            }),
          )
          .optional(),
      })
      .nullable(),
    wearer: z
      .object({
        at: timestamp,
        worldMapId: z.string(),
        position: point,
        bodyYawDeg: coordinate,
        headYawDeg: coordinate.nullable(),
      })
      .nullable(),
    items: z.array(itemSchema),
    camera: z
      .object({
        frameId: z.number().int().nonnegative(),
        capturedAt: timestamp,
        widthPx: z.number().int().positive(),
        heightPx: z.number().int().positive(),
        imageUrl: z.string(),
        boxes: z.array(
          z.object({
            itemId: z.string(),
            boxPx: z
              .tuple([coordinate, coordinate, coordinate, coordinate])
              .refine(([x1, y1, x2, y2]) => x2 > x1 && y2 > y1, 'Invalid box'),
          }),
        ),
      })
      .nullable(),
    navigation: z.object({
      state: z.enum([
        'idle',
        'guiding',
        'within_reach',
        'found',
        'paused',
        'unavailable',
      ]),
      targetItemId: z.string().nullable(),
      distanceM: z.number().nonnegative().nullable(),
      bearingDeg: coordinate.nullable(),
      bearingReference: z.enum(['head', 'body']).nullable(),
      audioPattern: z.enum(['off', 'beacon', 'steady', 'confirmation']),
      spokenInstruction: z.string().nullable(),
      updatedAt: timestamp,
    }),
    registrations: z.array(
      z.object({
        id: z.string(),
        status: z.enum([
          'photo_received',
          'waiting_for_label',
          'processing_label',
          'saved',
          'retake',
          'failed',
        ]),
        photoUrl: z.string().nullable(),
        recipientName: z.string().nullable(),
        itemId: z.string().nullable(),
        label: voiceLabel.nullable(),
        updatedAt: timestamp,
        message: z.string().nullable(),
      }),
    ),
    recentMemory: z.array(
      z.object({
        id: z.string(),
        itemId: z.string(),
        kind: z.enum(['seen', 'moved', 'label_saved']),
        at: timestamp,
        surface: z.string().nullable(),
      }),
    ),
    lastCommand: z
      .object({
        commandId: z.string(),
        status: z.enum(['pending', 'accepted', 'completed', 'rejected']),
        reason: z.string().nullable(),
      })
      .nullable(),
  }),
})

export type Snapshot = z.infer<typeof snapshotSchema>
export type DashboardData = Snapshot['data']
export type Item = z.infer<typeof itemSchema>
export type Registration = DashboardData['registrations'][number]
export type Command = { commandId: string; deviceId: string } & (
  { type: 'find'; itemId: string } | { type: 'stop' }
)
export const commandResponseSchema = z.object({
  commandId: z.string(),
  status: z.literal('pending'),
})

// What the wearer hears (docs/INTERFACES.md §6, `dashboard.sound` on /events): the phone reports every sound as it
// starts (a cue) and, 10 times a second while anything is audible, where each source is (a field). Directions are
// relative to the wearer's head: azimuth 0 ahead, +90 right, ±180 behind; elevation + up.
const azimuth = z.number().finite().min(-180).max(180)
const elevation = z.number().finite().min(-90).max(90)
const meters = z.number().finite().nonnegative()
const anchor = z.enum(['item', 'room', 'ahead'])
const soundCue = z.object({
  kind: z.literal('cue'),
  tDevice: z.number().finite(),
  cue: z.enum([
    'beep',
    'ding',
    'tone_on',
    'tone_off',
    'say',
    'label',
    'blip',
    'silence',
  ]),
  source: z.enum(['beacon', 'voice']),
  anchor,
  azimuthDeg: azimuth,
  elevationDeg: elevation,
  distanceM: meters,
  muffled: z.boolean().nullable(),
  text: z.string().nullable(),
  durationS: z.number().finite().nonnegative().nullable(),
  audioUrl: z.string().nullable(),
})
const fieldSource = {
  azimuthDeg: azimuth,
  elevationDeg: elevation,
  distanceM: meters,
}
const soundField = z.object({
  kind: z.literal('field'),
  tDevice: z.number().finite(),
  headYawDeg: z.number().finite().nullable(),
  beacon: z
    .object({ ...fieldSource, muffled: z.boolean().nullable() })
    .nullable(),
  voice: z.object({ ...fieldSource, anchor }).nullable(),
})
export const soundSchema = z.object({
  type: z.literal('dashboard.sound'),
  schemaVersion: z.literal(1),
  streamId: z.string(),
  sentAt: timestamp,
  sound: z.discriminatedUnion('kind', [soundCue, soundField]),
})
export type SoundMessage = z.infer<typeof soundSchema>
export type Sound = SoundMessage['sound']
export type SoundCue = z.infer<typeof soundCue>
export type SoundField = z.infer<typeof soundField>
