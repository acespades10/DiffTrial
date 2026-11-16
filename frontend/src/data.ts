import type { DashboardData } from "./types";

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers: { "Content-Type": "application/json", "X-DiffTrial-Local": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "The local service did not respond." }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "Check the form values and try again.",
    );
  }
  return response.json();
}

export async function loadDashboard(): Promise<DashboardData> {
  if (__DEMO__) {
    const response = await fetch(`${import.meta.env.BASE_URL}demo/index.json`);
    if (!response.ok)
      throw new Error(
        "Recorded results could not be loaded. Retry in a moment.",
      );
    const data = await response.json();
    if (data.schema_version !== "difftrial.demo.v1" || !data.recorded)
      throw new Error("Unsupported recorded bundle version.");
    return data;
  }
  const [runs, benchmarks, comparisons] = await Promise.all([
    api<DashboardData["runs"]>("/runs"),
    api<DashboardData["benchmarks"]>("/benchmarks"),
    api<DashboardData["comparisons"]>("/comparisons"),
  ]);
  return { runs, benchmarks, comparisons };
}

export const terminal = (status: string) =>
  [
    "completed",
    "cancelled",
    "interrupted",
    "infrastructure_error",
    "failed",
  ].includes(status);
export const label = (value: string) => value.replaceAll("_", " ");
export const date = (seconds: number) =>
  new Date(seconds * 1000).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
export function duration(run: {
  started: number | null;
  finished: number | null;
}) {
  if (!run.started || !run.finished) return "Not recorded";
  const seconds = Math.round(run.finished - run.started);
  return seconds < 60
    ? `${seconds}s`
    : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
export function download(content: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/plain" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
