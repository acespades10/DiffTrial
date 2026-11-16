import { defineConfig } from "@playwright/test";

const publishedURL = process.env.DIFFTRIAL_DEMO_URL;

export default defineConfig({
  testDir: "./e2e-demo",
  timeout: 30000,
  use: {
    baseURL:
      publishedURL || "http://127.0.0.1:4173/Agentic-Code-Review-Sandbox/",
    headless: true,
    channel: process.platform === "win32" ? "msedge" : undefined,
  },
  webServer: publishedURL
    ? undefined
    : {
        command: "npm run preview -- --mode demo --port 4173",
        url: "http://127.0.0.1:4173/Agentic-Code-Review-Sandbox/",
        reuseExistingServer: !process.env.CI,
      },
  reporter: "list",
});
