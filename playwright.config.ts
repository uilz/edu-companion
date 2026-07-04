import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for Conversation module E2E tests
 *
 * Targets:
 * - Desktop 1280x800 (主流程)
 * - Tablet  768x1024
 * - Mobile  375x667
 *
 * 启动：先 rebuild.sh 启动服务
 * 运行：npx playwright test
 * 调试：npx playwright test --headed
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
    ["json", { outputFile: "playwright-report/results.json" }],
  ],
  outputDir: "playwright-report/test-results",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://192.168.13.133:8080",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 5_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    {
      name: "tablet",
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 } },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 5"], viewport: { width: 375, height: 667 } },
    },
  ],
  // 不自动启动 dev server（依赖 rebuild.sh 已经启动的实例）
});
