import { defineConfig } from "@playwright/test";

// Runs against a live stack (docker compose up, or `make dev-api` + `make dev-web`).
//   E2E_BASE_URL     where the site is (default http://localhost:8080)
//   PW_CHROMIUM_PATH use an existing Chromium instead of `npx playwright install chromium`
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH, args: ["--no-sandbox"] } : {},
  },
});
