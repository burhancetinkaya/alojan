import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 30000,
  reporter: "list",
  use: {
    baseURL: process.env.ALOJAN_WEB_TEST_ORIGIN || "https://localhost:18443",
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
});
