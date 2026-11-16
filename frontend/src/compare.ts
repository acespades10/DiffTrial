import type { Comparison, Run } from "./types";

export function compareSelected(runs: Run[]): Comparison[] {
  const groups = new Map<string, Run[]>();
  for (const run of runs) {
    const key = JSON.stringify([
      run.task.source,
      run.limits,
      run.prompt_version,
      run.rubric_version,
      run.protocol ?? "local_worker",
      run.provider.kind,
      run.provider.model,
    ]);
    groups.set(key, [...(groups.get(key) ?? []), run]);
  }
  return [...groups.values()].map((group, index) => {
    const first = group[0];
    const eligible = group.filter(
      (r) =>
        ["completed", "failed"].includes(r.status) &&
        r.task.source.kind === "benchmark" &&
        (r.baseline.tests?.failed ?? 0) > 0,
    );
    const fixed = eligible.filter((r) => r.outcome === "fixed").length;
    return {
      cohort: `selected-${index + 1}`,
      task: first.task.title,
      version: first.task.source.version,
      provider: first.provider.kind,
      model: first.provider.model,
      total: group.length,
      eligible: eligible.length,
      fixed,
      fix_rate: eligible.length ? fixed / eligible.length : null,
      regressions: group.filter((r) => r.outcome === "regressed").length,
      infrastructure_errors: group.filter((r) =>
        ["infrastructure_error", "interrupted"].includes(r.status),
      ).length,
      failed_repairs: group.filter(
        (r) =>
          r.status === "failed" ||
          (r.status === "completed" &&
            !["fixed", "passing"].includes(r.outcome)),
      ).length,
      duration_seconds: group.reduce(
        (sum, r) =>
          sum +
          Math.max(0, (r.finished ?? r.created) - (r.started ?? r.created)),
        0,
      ),
      input_tokens: group.reduce(
        (sum, r) => sum + (r.usage.input_tokens ?? 0),
        0,
      ),
      output_tokens: group.reduce(
        (sum, r) => sum + (r.usage.output_tokens ?? 0),
        0,
      ),
      usage_available_runs: group.filter((r) => Object.keys(r.usage).length > 0)
        .length,
    };
  });
}
