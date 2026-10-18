import { test, expect } from '@playwright/test'
import { demoSnapshot } from '../src/data/demo'

test('saved items and logo load under /app/ without a connected iPhone', async ({
  page,
}) => {
  const value = demoSnapshot()
  value.data.items = [
    {
      id: 'saved-can',
      name: 'Diet Coke',
      photoUrl: '/media/items/saved-can.jpg',
      voiceLabel: null,
      lastSeen: null,
    },
  ]
  value.data.session = {
    ...value.data.session,
    id: '',
    deviceId: '',
    worldMapId: null,
  }
  value.data.devices.phone = {
    state: 'disconnected',
    lastMessageAt: null,
    tracking: 'unavailable',
  }
  value.data.devices.airpods = { state: 'unknown', lastMessageAt: null }
  value.data.map = null
  value.data.wearer = null
  value.data.camera = null
  value.data.navigation = {
    ...value.data.navigation,
    state: 'unavailable',
    targetItemId: null,
    distanceM: null,
    bearingDeg: null,
    bearingReference: null,
    audioPattern: 'off',
    spokenInstruction: null,
  }
  value.data.registrations = []
  value.data.recentMemory = []
  value.data.lastCommand = null
  await page.route('**/api/dashboard/snapshot', (route) =>
    route.fulfill({ json: value }),
  )
  await page.routeWebSocket('**/api/events', (ws) =>
    ws.send(JSON.stringify(value)),
  )
  await page.route('**/api/media/items/saved-can.jpg', async (route) => {
    const photo = await page.request.get(
      'http://127.0.0.1:5175/app/images/keys.jpg',
    )
    await route.fulfill({ response: photo })
  })
  await page.goto('http://127.0.0.1:5175/app/')
  await expect(
    page.getByText('1 object', { exact: false }).first(),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Diet Coke' })).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'No objects yet' }),
  ).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: 'Find diet coke' }),
  ).toBeDisabled()
  await expect(page.getByRole('alert')).toHaveCount(0)
  for (const selector of ['.brand img', '.object-detail .item-image img']) {
    await expect
      .poll(() =>
        page
          .locator(selector)
          .evaluate((img: HTMLImageElement) =>
            img.complete ? img.naturalWidth : 0,
          ),
      )
      .toBeGreaterThan(0)
  }
  await expect(page.locator('.brand img')).toHaveAttribute(
    'src',
    '/app/brand/marco-polo-mark.svg',
  )
})
