import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'

async function scenario(page: Page, name: string) {
  await page.getByRole('button', { name: 'Demo', exact: true }).click()
  await page.getByRole('button', { name, exact: true }).click()
}

test('objects, search, selection and explicit voice playback', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Objects', exact: true }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Play voice label' }),
  ).toBeVisible()
  expect(
    await page.locator('audio').evaluate((el: HTMLAudioElement) => el.paused),
  ).toBe(true)
  await page.getByRole('button', { name: 'Play voice label' }).click()
  await expect(
    page.getByRole('button', { name: 'Pause voice label' }),
  ).toBeVisible()
  await expect
    .poll(() =>
      page.locator('audio').evaluate((el: HTMLAudioElement) => el.duration),
    )
    .toBeGreaterThan(0.5)
  await page.getByRole('button', { name: 'Pause voice label' }).click()
  await page.getByRole('textbox', { name: 'Search objects' }).fill('glasses')
  await expect(
    page.getByRole('button', { name: /Reading glasses Desk/ }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: /Keys Coffee table/ }),
  ).toHaveCount(0)
  await page.getByRole('button', { name: /Reading glasses Desk/ }).click()
  await expect(
    page.getByRole('complementary', { name: 'Reading glasses details' }),
  ).toBeVisible()
  await page
    .getByRole('textbox', { name: 'Search objects' })
    .fill('does-not-exist')
  await expect(page.getByRole('heading', { name: 'No matches' })).toBeVisible()
  await page.getByRole('button', { name: 'Clear search' }).click()
  await expect(
    page.getByRole('button', { name: /Keys Coffee table/ }),
  ).toBeVisible()
  expect(errors).toEqual([])
})

test('find waits for acknowledgement, camera boxes align, stop returns to idle', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Find keys', exact: true }).click()
  await expect(
    page.getByRole('status').filter({ hasText: 'Request pending' }),
  ).toBeVisible()
  await expect(
    page.getByRole('status').filter({ hasText: 'Guidance active' }),
  ).toBeVisible()
  await expect(page.getByLabel('2.1 meters')).toBeVisible()
  await page.getByRole('button', { name: 'Camera', exact: true }).click()
  await expect(page.getByTestId('detection-box')).toBeVisible()
  const alignment = await page.locator('.camera-frame').evaluate((frame) => {
    const img = frame.querySelector('img')!.getBoundingClientRect()
    const box = frame
      .querySelector('[data-testid=detection-box]')!
      .getBoundingClientRect()
    return {
      left: (box.left - img.left) / img.width,
      top: (box.top - img.top) / img.height,
    }
  })
  expect(alignment.left).toBeCloseTo(375 / 1600, 2)
  expect(alignment.top).toBeCloseTo(120 / 900, 2)
  await page.getByRole('button', { name: 'Map', exact: true }).click()
  await page.getByRole('button', { name: 'Recenter' }).click()
  await expect(page.getByRole('button', { name: 'Recenter' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('button', { name: 'Stop finding' }).click()
  await expect(
    page.getByRole('heading', { name: 'Ready when you are' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Choose an object' }).click()
  await expect(
    page.getByRole('heading', { name: 'Objects', exact: true }),
  ).toBeVisible()
})

test('Photon drawer follows waiting to saved and supports escape/focus return', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'View request' }).click()
  await expect(
    page.getByRole('dialog', { name: 'Photon labels' }),
  ).toBeVisible()
  await expect(page.getByText('Awaiting label', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'View request' })).toBeFocused()
  await scenario(page, 'Photon label saved')
  await page.getByRole('button', { name: 'Photon labels', exact: true }).click()
  await expect(page.getByText('Label saved', { exact: true })).toBeVisible()
  await expect(page.getByText('The blue mug.', { exact: true })).toBeVisible()
})

test('near, found and moved states reflect phone data', async ({ page }) => {
  await page.goto('/#live')
  await scenario(page, 'Within reach')
  await expect(page.getByLabel('0.24 meters')).toBeVisible()
  await expect(
    page.getByText('Within reach. Reach forward.', { exact: true }),
  ).toBeVisible()
  await scenario(page, 'Object found')
  await expect(page.getByRole('heading', { name: 'Got it.' })).toBeVisible()
  await page.getByRole('button', { name: 'Back to objects' }).click()
  await scenario(page, 'Keys moved')
  await expect(
    page.getByRole('button', { name: /Keys Console table/ }),
  ).toBeVisible()
  await expect(page.getByText('Moved', { exact: true })).toBeVisible()
})

test('disconnection and tracking loss suppress directions without losing saved objects', async ({
  page,
}) => {
  await page.goto('/#live')
  await scenario(page, 'iPhone disconnected')
  await expect(page.getByLabel('2.1 meters')).toHaveCount(0)
  await expect(
    page.getByRole('button', { name: 'Stop finding' }),
  ).toBeDisabled()
  await page.getByRole('link', { name: 'Objects', exact: true }).click()
  await expect(
    page.getByRole('button', { name: /Keys Coffee table/ }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', { name: 'Find keys', exact: true }),
  ).toBeDisabled()
  await scenario(page, 'Restoring position')
  await page.getByRole('link', { name: 'Live', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Restoring position' }),
  ).toBeVisible()
  await expect(page.getByLabel('2.1 meters')).toHaveCount(0)
})

test('empty library, missing map and broken media have honest fallbacks', async ({
  page,
}) => {
  await page.route('**/images/keys.jpg', (route) => route.abort())
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Keys', exact: true }),
  ).toBeVisible()
  await expect(page.locator('.object-detail .item-image img')).toHaveCount(0)
  await scenario(page, 'Map unavailable')
  await page.getByRole('link', { name: 'Live', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'Map unavailable' }),
  ).toBeVisible()
  await scenario(page, 'No objects')
  await page.getByRole('link', { name: 'Objects', exact: true }).click()
  await expect(
    page.getByRole('heading', { name: 'No objects yet' }),
  ).toBeVisible()
  await page
    .getByRole('button', { name: 'Photon labels', exact: true })
    .first()
    .click()
  await expect(
    page.getByRole('heading', { name: 'No label requests' }),
  ).toBeVisible()
})

for (const width of [1440, 768, 390]) {
  test(`responsive and accessible at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await expect(
      page.getByRole('heading', { name: 'Objects', exact: true }),
    ).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await page.screenshot({
      path: `test-results/objects-${width}.png`,
      fullPage: true,
    })
    await page.getByRole('link', { name: 'Live', exact: true }).click()
    await expect(page.getByLabel('2.1 meters')).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await page.screenshot({
      path: `test-results/live-${width}.png`,
      fullPage: true,
    })
    await page.getByRole('button', { name: 'Camera', exact: true }).click()
    await expect(page.getByTestId('detection-box')).toBeVisible()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    await page.getByRole('button', { name: 'Map', exact: true }).click()
    await expect(
      page.getByRole('img', { name: /Sound at 145 degrees/ }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Listen in' })).toBeVisible()
  })
}

test('what the wearer hears runs through the map and the guidance panel, from Polo to the label', async ({
  page,
}) => {
  test.setTimeout(45000)
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/#live')
  await scenario(page, 'Finding keys, start to finish')
  const panel = page.getByRole('complementary', { name: 'Navigation guidance' })
  await expect(
    panel.getByText('Polo! Behind you, two steps, on the table.'),
  ).toBeVisible()
  await expect(
    panel.getByText('Marco, from behind, on the right'),
  ).toBeVisible()
  await expect(page.locator('.map-head.sounding')).toBeVisible()
  await expect(panel.getByText('Playing in AirPods: beacon')).toBeVisible({
    timeout: 8000,
  })
  await expect(panel.getByText('Within reach, on the table.')).toBeVisible({
    timeout: 15000,
  })
  await expect(panel.getByText('Your house keys.')).toBeVisible({
    timeout: 12000,
  })
  const listen = page.getByRole('button', { name: 'Listen in' })
  await expect(listen).toHaveAttribute('aria-pressed', 'false')
  await listen.click()
  await expect(listen).toHaveAttribute('aria-pressed', 'true')
  await listen.click()
  await expect(listen).toHaveAttribute('aria-pressed', 'false')
  await expect(
    page.getByRole('button', { name: 'Sound', exact: true }),
  ).toHaveCount(0)
  expect(errors).toEqual([])
})

test('away from Live, the line in the AirPods still shows', async ({
  page,
}) => {
  await page.goto('/')
  await scenario(page, 'Finding keys, start to finish')
  await expect(
    page.getByRole('status').filter({ hasText: 'In the AirPods' }),
  ).toContainText('Polo! Behind you, two steps, on the table.')
})
