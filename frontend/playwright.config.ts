import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    channel: process.platform === "win32" ? "msedge" : undefined,
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
  },
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
});
