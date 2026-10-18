import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chrome',
      use: {
        ...devices['Desktop Chrome'],
        channel: process.env.CI ? undefined : 'chrome',
      },
    },
  ],
  webServer: [
    {
      command: 'npm run dev -- --strictPort',
      env: { VITE_DATA_SOURCE: 'demo' },
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 5174 --strictPort',
      env: { VITE_DATA_SOURCE: 'api' },
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 5175 --strictPort --base=/app/',
      env: { VITE_DATA_SOURCE: 'api' },
      url: 'http://127.0.0.1:5175/app/',
      reuseExistingServer: !process.env.CI,
    },
  ],
})
