import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import fs from "node:fs";

const benchmarks = JSON.parse(
  fs.readFileSync("../benchmarks/catalog.json", "utf8"),
);
const report = {
  exit_code: 1,
  report_valid: true,
  passed: 1,
  failed: 1,
  skipped: 0,
  duration: 0.2,
  log: "Test fixture log",
  cases: [
    { name: "existing", status: "passed" },
    { name: "regression", status: "failed" },
  ],
};
const run = {
  id: "browser-fixture-001",
  status: "completed",
  stage: "completed",
  outcome: "fixed",
  verdict: "accept",
  provider: {
    kind: "codexlb",
    model: "browser-test-double",
    transport: "responses",
  },
  created: 1700000000,
  started: 1700000001,
  finished: 1700000005,
  usage: { input_tokens: 20, output_tokens: 10 },
  limits: {
    attempts: 2,
    run_seconds: 900,
    command_seconds: 300,
    memory_mb: 512,
    cpus: 1,
  },
  task: {
    id: "task",
    title: "Browser fixture repair",
    issue: "Fixture content for browser tests only.",
    profile: "python",
    source: {
      kind: "benchmark",
      benchmark_id: "py-intervals",
      version: "1",
      tree_sha256: "a".repeat(64),
      evaluation: "protected_regression_tests",
    },
  },
  baseline: { tests: report, static: { ...report, exit_code: 0 } },
  attempts: [
    {
      number: 1,
      patch:
        "--- a/src/repair.py\n+++ b/src/repair.py\n@@ -1 +1 @@\n-return 0\n+return 1\n",
      reports: {
        tests: {
          ...report,
          exit_code: 0,
          failed: 0,
          passed: 2,
          cases: report.cases.map((c) => ({ ...c, status: "passed" })),
        },
        static: { ...report, exit_code: 0 },
      },
      review: {
        summary: "Browser test review.",
        verdict: "accept",
        findings: [
          { rule: "R01", severity: "info", message: "Fixture finding" },
        ],
      },
    },
  ],
  events: [
    {
      id: 1,
      created: 1700000002,
      kind: "role",
      payload: { role: "planner", summary: "Browser fixture plan." },
    },
  ],
  prompt_version: "repair-v1",
  rubric_version: "review-v1",
};

async function mock(page: Page, runs = [run]) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = {};
    if (path.endsWith("/runs"))
      body = route.request().method() === "POST" ? run : runs;
    else if (path.endsWith("/benchmarks")) body = benchmarks;
    else if (path.endsWith("/comparisons")) body = [];
    else if (path.endsWith("/providers"))
      body = {
        config: {
          kind: "codexlb",
          transport: "responses",
          endpoint: "https://provider.example/v1",
          model: "test",
          key_env: "CODEX_LB_API_KEY",
        },
      };
    else if (path.endsWith("/health"))
      body = { docker: { message: "Test-only Docker status" }, ollama: { available: true } };
    else if (path.endsWith("/tasks")) body = { id: "task" };
    else if (path.endsWith("/models")) body = { models: ["local-test"] };
    else if (path.endsWith("/export")) {
      await route.fulfill({
        contentType: "application/json",
        headers: {
          "Content-Disposition": 'attachment; filename="test-evidence.json"',
        },
        body: JSON.stringify({ run }),
      });
      return;
    }
    await route.fulfill({ json: body });
  });
}

test("filters, comparison selection, run evidence, downloads and themes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await mock(page);
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Every patch has a record.");
  await page.getByLabel("Find a run").fill("missing");
  await expect(page.getByText("No matching runs")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Outcome", { exact: true }).selectOption("failing");
  await expect(page.getByText("No matching runs")).toBeVisible();
  await page.getByLabel("Outcome", { exact: true }).selectOption("all");
  await page.getByRole("checkbox").check();
  await page.getByRole("link", { name: "Compare 1 selected" }).click();
  await expect(page.locator(".comparison-list dd").first()).toContainText("1 / 1");
  await page.getByRole("button", { name: "Clear selection" }).click();
  await expect(page.getByText("No comparable evidence yet")).toBeVisible();
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await page.getByRole("button", { name: "Refresh results" }).click();
  await page.getByRole("link", { name: run.task.title, exact: true }).click();
  await page.getByText("Execution log", { exact: true }).first().click();
  await expect(page.getByText("Test fixture log").first()).toBeVisible();
  const diff = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download diff" }).click();
  expect((await diff).suggestedFilename()).toBe("attempt-1.diff");
  const bundle = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download evidence" }).click();
  expect((await bundle).suggestedFilename()).toBe(`difftrial-${run.id}.json`);
  await page.getByText("Static analysis log", { exact: true }).click();
  await page.getByText("Source provenance and execution limits").click();
  await expect(page.getByText("900s deadline", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  expect(errors).toEqual([]);
});

test("local settings, model discovery, imports and creation work", async ({
  page,
}) => {
  await mock(page, []);
  await page.goto("/#new");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(
    page.getByText("Provider settings saved locally."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Check connection" }).click();
  await expect(
    page.getByText("Connection verified with an actual generation request."),
  ).toBeVisible();
  await page.getByLabel("Provider", { exact: true }).selectOption("compatible");
  await page.getByLabel("Transport", { exact: true }).selectOption("chat");
  await page
    .getByLabel("Endpoint", { exact: true })
    .fill("https://provider.example/v1");
  await page.getByLabel("Model", { exact: true }).fill("test");
  await page.getByLabel("Provider", { exact: true }).selectOption("ollama");
  await page.getByRole("button", { name: "Load installed models" }).click();
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue(
    "local-test",
  );
  await page.getByLabel("Source", { exact: true }).selectOption("github");
  await page
    .getByLabel("Repository URL")
    .fill("https://github.com/example/repo");
  await page
    .getByLabel("Issue description")
    .fill("Repair the boundary condition.");
  await page.getByLabel("Runner profile").selectOption("typescript");
  await page.getByText("Execution limits", { exact: true }).click();
  await page.getByLabel("Run deadline (seconds)").fill("120");
  await page.getByLabel("Command timeout (seconds)").fill("30");
  await page.getByText("Optional pricing", { exact: true }).click();
  await page.getByLabel("Input USD per million tokens").fill("1");
  await page.getByLabel("Output USD per million tokens").fill("2");
  const taskRequest = page.waitForRequest((r) => r.url().endsWith("/tasks"));
  await page.getByRole("button", { name: "Queue repair run" }).click();
  expect((await taskRequest).postDataJSON()).toMatchObject({
    profile: "typescript",
    issue: "Repair the boundary condition.",
  });
});

test("empty, loading, error and retry states", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    await new Promise((r) => setTimeout(r, 500));
    await route.fulfill({
      status: 503,
      json: { detail: "Service unavailable in test" },
    });
  });
  await page.goto("/");
  await expect(page.getByRole("status")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveText(
    "Service unavailable in test",
  );
  await page.unrouteAll();
  await mock(page, []);
  await page.getByRole("button", { name: "Retry loading" }).click();
  await expect(page.getByText("No runs recorded yet")).toBeVisible();
});

for (const width of [390, 768, 1024, 1440]) {
  test(`responsive evidence and keyboard tabs at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await mock(page);
    await page.goto(`/#runs/${run.id}`);
    for (const theme of ["light", "dark"]) {
      if (theme === "dark")
        await page
          .getByRole("button", { name: "Switch to dark theme" })
          .click();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      if (width < 1100) {
        await page.getByRole("tab", { name: "evidence", exact: true }).click();
        await expect(
          page.getByText("Baseline tests", { exact: true }),
        ).toBeVisible();
        await page.keyboard.press("ArrowRight");
        await expect(
          page.getByRole("tab", { name: "review", exact: true }),
        ).toBeFocused();
        await expect(page.getByText("Fixture finding")).toBeVisible();
        await page.keyboard.press("End");
        await expect(page.getByText("Browser fixture plan.")).toBeVisible();
        await page.keyboard.press("Home");
      }
      await page.screenshot({
        path: `test-results/detail-${width}-${theme}.png`,
        fullPage: true,
      });
    }
    await page.getByRole("link", { name: "Benchmarks", exact: true }).click();
    await page.getByLabel("Language").selectOption("python");
    await expect(page.locator(".benchmark-list article")).toHaveCount(6);
    await page.getByLabel("Language").selectOption("typescript");
    await expect(page.locator(".benchmark-list article")).toHaveCount(6);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}
