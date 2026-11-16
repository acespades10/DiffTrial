import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";

test("published bundles contain measured successes and an unsuccessful control", async ({
  page,
  request,
}) => {
  const response = await request.get("demo/index.json");
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.runs).toHaveLength(3);
  expect(
    data.runs.filter((r: { outcome: string }) => r.outcome === "fixed"),
  ).toHaveLength(2);
  expect(
    data.runs.filter((r: { outcome: string }) => r.outcome === "failing"),
  ).toHaveLength(1);
  for (const run of data.runs) {
    expect(run.protocol).toBe("staged_ci");
    const bundle = await (await request.get(`demo/${run.id}.json`)).json();
    for (const artifact of bundle.artifacts) {
      expect(createHash("sha256").update(artifact.content).digest("hex")).toBe(
        artifact.sha256,
      );
    }
  }
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("./");
  await expect(page.getByText("Recorded demo", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Create repair run" }),
  ).toHaveCount(0);
  await page
    .getByRole("link", { name: data.runs[0].task.title, exact: true })
    .first()
    .click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download evidence" }).click();
  expect((await download).suggestedFilename()).toBe(
    `difftrial-${data.runs[0].id}.json`,
  );
  for (const width of [390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ["light", "dark"]) {
      await page.evaluate((value) => {
        localStorage.setItem("difftrial-theme", value);
      }, theme);
      await page.reload();
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `test-results/recorded-${width}-${theme}.png`,
        fullPage: true,
      });
    }
  }
  await page.getByRole("link", { name: "Compare", exact: true }).click();
  await expect(page.locator(".comparison-list article")).toHaveCount(3);
  await page.getByRole("link", { name: "Benchmarks", exact: true }).click();
  await expect(page.locator(".benchmark-list article")).toHaveCount(12);
  const guide = await request.get("guide.html");
  expect(guide.ok()).toBeTruthy();
  expect(await guide.text()).toContain("Architecture and methodology");
  expect(errors).toEqual([]);
});
