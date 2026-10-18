import { test, expect } from '@playwright/test'
import type { Page, WebSocketRoute } from '@playwright/test'
import { demoSnapshot } from '../src/data/demo'
import type { Command } from '../src/lib/schema'

test.use({ baseURL: 'http://127.0.0.1:5174' })
async function mockApi(page: Page) {
  const value = demoSnapshot()
  let socket!: WebSocketRoute
  let command: Command | undefined
  await page.route('**/api/dashboard/snapshot', (route) =>
    route.fulfill({ json: value }),
  )
  await page.routeWebSocket('**/api/events', (ws) => {
    socket = ws
    ws.send(JSON.stringify(value))
  })
  await page.route('**/api/dashboard/commands', async (route) => {
    command = route.request().postDataJSON() as Command
    await route.fulfill({
      status: 202,
      json: { commandId: command.commandId, status: 'pending' },
    })
  })
  const publish = () => {
    value.sequence++
    const time = new Date().toISOString()
    value.sentAt = time
    value.data.navigation.updatedAt = time
    value.data.devices.phone.lastMessageAt = time
    if (value.data.wearer) value.data.wearer.at = time
    socket.send(JSON.stringify(value))
  }
  return {
    value,
    publish,
    get command() {
      return command
    },
    get socket() {
      return socket
    },
  }
}

test('Listen in preserves current phone cue variants through the live event feed', async ({
  page,
}) => {
  // Observe real Web Audio buffers without playing sound from a browser test.
  await page.addInitScript(() => {
    const buffers: { length: number; loop: boolean; sample: number }[] = []
    Object.assign(window, { testSoundBuffers: buffers })
    const start = AudioBufferSourceNode.prototype.start
    AudioBufferSourceNode.prototype.start = function () {
      if (this.buffer)
        buffers.push({
          length: this.buffer.length,
          loop: this.loop,
          sample: this.buffer.getChannelData(0)[500],
        })
      this.disconnect()
      start.call(this)
    }
  })
  const api = await mockApi(page)
  await page.goto('/#live')
  const listen = page.getByRole('button', { name: 'Listen in', exact: true })
  await expect(listen).toBeVisible()
  const send = (cue: string, variant?: string, handStep?: number) =>
    api.socket.send(
      JSON.stringify({
        type: 'dashboard.sound',
        schemaVersion: 1,
        streamId: api.value.streamId,
        sentAt: new Date().toISOString(),
        sound: {
          kind: 'cue',
          tDevice: 5,
          cue,
          source: 'beacon',
          anchor: 'item',
          azimuthDeg: 30,
          elevationDeg: -20,
          distanceM: 1.5,
          muffled: variant === 'behind',
          text: null,
          durationS: null,
          audioUrl: null,
          variant,
          handStep,
        },
      }),
    )
  const buffers = () =>
    page.evaluate(
      () =>
        (
          window as unknown as {
            testSoundBuffers: {
              length: number
              loop: boolean
              sample: number
            }[]
          }
        ).testSoundBuffers,
    )
  send('beep', 'on_beam')
  // Ensure the event has reached the store before enabling playback: no replay on opt-in.
  await expect(page.locator('.sound-ripple').first()).toBeVisible()
  expect(await buffers()).toEqual([])
  await listen.click()
  for (const variant of ['on_beam', 'off_beam', 'behind', 'here'])
    send('beep', variant)
  for (let step = 0; step < 6; step++) send('beep', 'hand_ping', step)
  send('ding', 'arrive')
  send('tone_on', 'contact')
  await expect.poll(async () => (await buffers()).length).toBe(12)
  const played = await buffers()
  // Browser sample rates vary; compare lengths relative to the one-second contact buffer.
  const rate = played[11].length
  expect(played.map((b) => b.length)).toEqual(
    [0.07, 0.11, 0.14, 0.09, ...Array(6).fill(0.06), 0.62, 1].map((s) =>
      Math.round(s * rate),
    ),
  )
  expect(new Set(played.slice(4, 10).map((b) => b.sample)).size).toBe(6)
  expect(played[11].loop).toBe(true)
  send('tone_off')
  await listen.click()
})

test('real adapter fetches, receives snapshots and waits for a matching command acknowledgement', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Objects', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Demo', exact: true }),
  ).toHaveCount(0)
  await page.getByRole('button', { name: 'Find keys', exact: true }).click()
  await expect.poll(() => api.command?.type).toBe('find')
  await expect(
    page.getByRole('status').filter({ hasText: 'Request pending' }),
  ).toBeVisible()
  api.value.data.lastCommand = {
    commandId: api.command!.commandId,
    status: 'accepted',
    reason: null,
  }
  api.publish()
  await expect(
    page.getByRole('status').filter({ hasText: 'Guidance active' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Stop finding' }).click()
  await expect.poll(() => api.command?.type).toBe('stop')
  api.value.data.navigation = {
    state: 'idle',
    targetItemId: null,
    distanceM: null,
    bearingDeg: null,
    bearingReference: null,
    audioPattern: 'off',
    spokenInstruction: null,
    updatedAt: new Date().toISOString(),
  }
  api.value.data.lastCommand = {
    commandId: api.command!.commandId,
    status: 'accepted',
    reason: null,
  }
  api.publish()
  await expect(
    page.getByRole('heading', { name: 'Ready when you are' }),
  ).toBeVisible()
})

test('socket loss retains memory, hides cues and reconnects', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.goto('/#live')
  await expect(page.getByLabel('2.1 meters')).toBeVisible()
  await api.socket.close()
  await expect(
    page.getByText('Connection lost. Showing last-seen memory.', {
      exact: true,
    }),
  ).toBeVisible()
  await expect(page.getByLabel('2.1 meters')).toHaveCount(0)
  api.value.sequence += 10
  await expect(page.getByLabel('2.1 meters')).toBeVisible({ timeout: 5000 })
  await page.getByRole('link', { name: 'Objects', exact: true }).click()
  await expect(
    page.getByRole('button', { name: /Keys Coffee table/ }),
  ).toBeVisible()
})

test('out-of-order messages, unknown messages and invalid camera dimensions do not corrupt the screen', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.goto('/#live')
  await expect(page.getByLabel('2.1 meters')).toBeVisible()
  api.publish()
  const old = structuredClone(api.value)
  old.sequence = 0
  old.data.items = []
  api.socket.send(JSON.stringify(old))
  api.socket.send(JSON.stringify({ type: 'phone.telemetry' }))
  await expect(
    page.getByRole('heading', { name: 'Keys', exact: true }),
  ).toBeVisible()
  api.value.data.camera!.widthPx = 999
  api.publish()
  await page.getByRole('button', { name: 'Camera', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Frame unavailable' }),
  ).toBeVisible()
  await expect(page.getByTestId('detection-box')).toHaveCount(0)
})

test('HTTP errors and rejected phone commands show actionable feedback', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.route('**/api/dashboard/commands', (route) =>
    route.fulfill({
      status: 409,
      json: {
        error: { code: 'command_pending', message: 'The phone is busy.' },
      },
    }),
  )
  await page.goto('/')
  await page.getByRole('button', { name: 'Find keys', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('The phone is busy.')
  await expect(
    page.getByRole('button', { name: 'Retry', exact: true }),
  ).toBeVisible()
  const calls: string[] = []
  await page.route('**/api/dashboard/commands', async (route) => {
    const command = route.request().postDataJSON() as Command
    calls.push(command.commandId)
    await route.fulfill({
      status: 202,
      json: { commandId: command.commandId, status: 'pending' },
    })
  })
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect.poll(() => calls.length).toBe(1)
  api.value.data.lastCommand = {
    commandId: calls[0],
    status: 'rejected',
    reason: 'Please reconnect your iPhone.',
  }
  api.publish()
  await expect(page.getByRole('alert')).toContainText(
    'Please reconnect your iPhone.',
  )
})

test('authentication and malformed initial data never silently switch to demo', async ({
  page,
}) => {
  await page.route('**/api/dashboard/snapshot', (route) =>
    route.fulfill({ status: 403, json: { detail: 'Forbidden' } }),
  )
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('Dashboard access denied')
  await expect(
    page.getByRole('heading', { name: 'Waiting for the server' }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Demo', exact: true }),
  ).toHaveCount(0)
})

test('invalid payloads show a contract error without fabricating objects', async ({
  page,
}) => {
  await page.route('**/api/dashboard/snapshot', (route) =>
    route.fulfill({ json: { type: 'dashboard.snapshot', schemaVersion: 2 } }),
  )
  await page.routeWebSocket('**/api/events', (ws) =>
    ws.send(JSON.stringify({ type: 'dashboard.snapshot', schemaVersion: 2 })),
  )
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText(
    'does not match the dashboard contract',
  )
  await expect(
    page.getByRole('heading', { name: 'Waiting for the server' }),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Keys', exact: true }),
  ).toHaveCount(0)
})

test('a live socket with no updates becomes stale, then recovers from a fresh snapshot', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.goto('/#live')
  await expect(page.getByLabel('2.1 meters')).toBeVisible()
  await expect(
    page.getByText('Connection lost. Showing last-seen memory.', {
      exact: true,
    }),
  ).toBeVisible({ timeout: 6000 })
  await expect(page.getByLabel('2.1 meters')).toHaveCount(0)
  api.publish()
  await expect(page.getByLabel('2.1 meters')).toBeVisible()
})

test('a silent socket automatically refetches current state and resumes without a page refresh', async ({
  page,
}) => {
  const api = await mockApi(page)
  let loads = 0
  await page.route('**/api/dashboard/snapshot', (route) => {
    if (++loads > 1) {
      api.value.sequence++
      const time = new Date().toISOString()
      api.value.sentAt = time
      api.value.data.navigation.updatedAt = time
      api.value.data.devices.phone.lastMessageAt = time
      api.value.data.wearer!.at = time
    }
    return route.fulfill({ json: api.value })
  })
  await page.goto('/#live')
  await expect(page.getByLabel('2.1 meters')).toBeVisible()
  // StrictMode may send and cancel an extra startup request. Recovery must
  // fetch again after startup, regardless of how many requests startup made.
  const startupLoads = loads
  await expect(
    page.getByText('Connection lost. Showing last-seen memory.', {
      exact: true,
    }),
  ).toBeVisible({ timeout: 6000 })
  await expect
    .poll(() => loads, { timeout: 10000 })
    .toBeGreaterThan(startupLoads)
  await expect(page.getByLabel('2.1 meters')).toBeVisible()
  await expect(page.locator('.position-status')).toHaveText('Live position')
})

for (const reset of ['session', 'wearer'] as const) {
  test(`${reset} map reset suppresses live position while preserving last-seen descriptions`, async ({
    page,
  }) => {
    const api = await mockApi(page)
    await page.goto('/#live')
    await expect(page.locator('.position-status')).toHaveText('Live position')
    await expect(page.getByRole('button', { name: 'Recenter' })).toBeEnabled()
    if (reset === 'session') api.value.data.session.worldMapId = 'new-map'
    else api.value.data.wearer!.worldMapId = 'new-map'
    api.publish()
    await expect(
      page.getByRole('heading', { name: 'Location unavailable' }),
    ).toBeVisible()
    await expect(page.locator('.position-status')).toHaveText(
      'Position unavailable',
    )
    await expect(
      page.locator('.room-map text').filter({ hasText: /^You$/ }),
    ).toHaveCount(0)
    await expect(page.locator('.room-map line[stroke-dasharray]')).toHaveCount(
      0,
    )
    await expect(page.getByRole('button', { name: 'Recenter' })).toBeDisabled()
    await expect(page.getByLabel('2.1 meters')).toHaveCount(0)
    await page.getByRole('link', { name: 'Objects', exact: true }).click()
    await expect(
      page.getByRole('button', { name: /Keys Coffee table/ }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Find keys', exact: true }),
    ).toBeDisabled()
  })
}

test('a missing camera waits, an actual image failure is reported, and a new frame recovers', async ({
  page,
}) => {
  const api = await mockApi(page)
  const camera = structuredClone(api.value.data.camera!)
  api.value.data.camera = null
  await page.route('**/images/failed-camera.jpg', (route) => route.abort())
  await page.goto('/#live')
  await page.getByRole('button', { name: 'Camera', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Waiting for camera', exact: true }),
  ).toBeVisible()
  api.value.data.camera = { ...camera, imageUrl: '/images/failed-camera.jpg' }
  api.publish()
  await expect(
    page.getByRole('heading', { name: 'Frame unavailable', exact: true }),
  ).toBeVisible()
  api.value.data.camera = null
  api.publish()
  await expect(
    page.getByRole('heading', { name: 'Waiting for camera', exact: true }),
  ).toBeVisible()
  api.value.data.camera = { ...camera, frameId: camera.frameId + 1 }
  api.publish()
  await expect(
    page.getByRole('img', { name: 'Chest camera preview' }),
  ).toBeVisible()
  await expect(page.getByTestId('detection-box')).toHaveCount(1)
  api.value.data.devices.phone.state = 'disconnected'
  api.publish()
  await expect(
    page.getByRole('heading', { name: 'Camera disconnected', exact: true }),
  ).toBeVisible()
})

test('a replacement voice label recovers after a media failure', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.route('**/audio/keys.wav', (route) => route.abort())
  await page.goto('/')
  await page.getByRole('button', { name: 'Play voice label' }).click()
  await expect(
    page.getByText('Audio unavailable', { exact: true }),
  ).toBeVisible()
  api.value.data.items[0].voiceLabel!.audioUrl = '/audio/keys.wav?new-label'
  api.publish()
  await expect(
    page.getByRole('button', { name: 'Play voice label' }),
  ).toBeEnabled()
  await page.getByRole('button', { name: 'Play voice label' }).click()
  await expect
    .poll(() =>
      page.locator('audio').evaluate((el: HTMLAudioElement) => el.duration),
    )
    .toBeGreaterThan(0.5)
})

test('a newly saved Photon registration joins the library with no invented location', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Objects', exact: true }),
  ).toBeVisible()
  const label = {
    audioUrl: null,
    transcript: 'Your water bottle.',
    authorName: null,
    durationSeconds: null,
    createdAt: new Date().toISOString(),
  }
  api.value.data.items.push({
    id: 'bottle',
    name: 'Water bottle',
    photoUrl: null,
    voiceLabel: label,
    lastSeen: null,
  })
  api.value.data.registrations.unshift({
    id: 'bottle-label',
    status: 'saved',
    photoUrl: null,
    recipientName: null,
    itemId: 'bottle',
    label,
    updatedAt: new Date().toISOString(),
    message: null,
  })
  api.publish()
  await page
    .getByRole('button', { name: /Water bottle Location not recorded yet/ })
    .click()
  await expect(
    page.getByText('Your water bottle.', { exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Find water bottle', exact: true }),
  ).toBeDisabled()
  await page.getByRole('button', { name: /Photon labels/ }).click()
  await expect(page.getByRole('combobox', { name: 'Request' })).toHaveValue(
    'bottle-label',
  )
  await expect(page.getByText('Label saved', { exact: true })).toBeVisible()
})

test('what the wearer hears arrives between snapshots and shows in the guidance panel', async ({
  page,
}) => {
  const api = await mockApi(page)
  await page.goto('/#live')
  const panel = page.getByRole('complementary', { name: 'Navigation guidance' })
  await expect(panel.getByLabel('2.1 meters')).toBeVisible()
  const sound = (value: object, streamId = api.value.streamId) =>
    api.socket.send(
      JSON.stringify({
        type: 'dashboard.sound',
        schemaVersion: 1,
        streamId,
        sentAt: new Date().toISOString(),
        sound: value,
      }),
    )
  const cue = {
    kind: 'cue',
    tDevice: 10,
    source: 'beacon',
    anchor: 'item',
    azimuthDeg: -90,
    elevationDeg: 0,
    distanceM: 1.5,
    muffled: false,
    text: null,
    durationS: null,
    audioUrl: null,
  }
  api.publish()
  sound({ ...cue, cue: 'beep' })
  await expect(panel.getByText('Playing in AirPods: beacon')).toBeVisible()
  await expect(
    panel.getByRole('img', {
      name: 'Sound at -90 degrees from where the wearer faces',
    }),
  ).toBeVisible()
  api.publish()
  sound({
    ...cue,
    cue: 'say',
    source: 'voice',
    muffled: null,
    text: 'Polo! On your left, two steps.',
    durationS: 2.4,
  })
  await expect(panel.getByText('Polo! On your left, two steps.')).toBeVisible()
  await expect(panel.getByText('Marco, from the left')).toBeVisible()
  sound(
    {
      ...cue,
      cue: 'say',
      source: 'voice',
      text: 'Not from this server.',
      durationS: 2,
    },
    'another-stream',
  )
  sound({ ...cue, cue: 'whistle' })
  api.publish()
  await expect(panel.getByText('Not from this server.')).toHaveCount(0)
})
