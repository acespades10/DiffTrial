import { describe, expect, it } from "vitest";
import { compareSelected } from "./compare";
import type { Run } from "./types";

const run = {
  provider: { kind: "codexlb", model: "test" },
  task: { title: "task", source: { kind: "benchmark", version: "1" } },
  limits: { command_seconds: 30 },
  prompt_version: "v1",
  rubric_version: "v1",
  status: "completed",
  outcome: "fixed",
  baseline: { tests: { failed: 1 } },
  usage: {},
  created: 0,
  started: 1,
  finished: 3,
} as Run;
describe("comparison denominators", () => {
  it("excludes infrastructure errors from eligible repairs", () => {
    const result = compareSelected([
      run,
      { ...run, status: "infrastructure_error", outcome: "not_run" },
    ]);
    expect(result[0]).toMatchObject({
      total: 2,
      eligible: 1,
      fixed: 1,
      fix_rate: 1,
      infrastructure_errors: 1,
    });
  });
  it("separates different execution limits", () => {
    expect(
      compareSelected([
        run,
        { ...run, limits: { ...run.limits, command_seconds: 60 } },
      ]),
    ).toHaveLength(2);
  });
  it("does not label imported repository passes as issue fixes", () => {
    const result = compareSelected([
      {
        ...run,
        task: { ...run.task, source: { ...run.task.source, kind: "github" } },
      },
    ]);
    expect(result[0].fix_rate).toBeNull();
    expect(result[0].eligible).toBe(0);
  });
});
