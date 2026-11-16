import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  api,
  date,
  download,
  duration,
  label,
  loadDashboard,
  terminal,
} from "./data";
import type {
  Attempt,
  Benchmark,
  DashboardData,
  Provider,
  Report,
  Run,
} from "./types";
import { compareSelected } from "./compare";

const initialProvider: Provider = {
  kind: "codexlb",
  transport: "responses",
  endpoint: "",
  model: "",
  key_env: "CODEX_LB_API_KEY",
};

function State({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="state">
      <h2>{title}</h2>
      {children}
    </div>
  );
}

function TestReport({ title, report }: { title: string; report?: Report }) {
  return (
    <section className="report">
      <div className="section-heading">
        <h3>{title}</h3>
        <span className="mono">
          {report ? `exit ${report.exit_code}` : "Not run"}
        </span>
      </div>
      {report ? (
        <>
          <p>
            <strong>{report.passed ?? 0} passed</strong>
            <span className={report.failed ? "failure" : ""}>
              {" "}
              · {report.failed ?? 0} failed
            </span>{" "}
            · {report.skipped ?? 0} skipped
          </p>
          {!report.report_valid && (
            <p className="failure">
              No valid test report. This is not a passing result.
            </p>
          )}
          <ul className="cases">
            {report.cases.map((c, i) => (
              <li key={`${c.name}-${i}`}>
                <span className={c.status === "passed" ? "success" : "failure"}>
                  {label(c.status)}
                </span>
                <code>{c.name}</code>
              </li>
            ))}
          </ul>
          <details>
            <summary>Execution log</summary>
            <pre>{report.log || "No output captured."}</pre>
          </details>
        </>
      ) : (
        <p className="muted">The runner has not recorded this check.</p>
      )}
    </section>
  );
}

function RunDetail({ run, reload }: { run: Run; reload: () => void }) {
  const [attemptIndex, setAttemptIndex] = useState(0);
  const [pane, setPane] = useState("patch");
  const [notice, setNotice] = useState("");
  const tabs = ["patch", "evidence", "review", "activity"];
  const attempt: Attempt | undefined =
    run.attempts[attemptIndex] ?? run.attempts.at(-1);
  useEffect(() => {
    setAttemptIndex(Math.max(0, run.attempts.length - 1));
  }, [run.id, run.attempts.length]);
  async function cancel() {
    try {
      await api(`/runs/${run.id}/cancel`, "POST");
      setNotice(
        "Cancellation requested. The worker will stop the active operation.",
      );
      reload();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  async function exportEvidence() {
    try {
      const result = __DEMO__
        ? await fetch(`${import.meta.env.BASE_URL}demo/${run.id}.json`).then(async response => {
            if (!response.ok) throw new Error("Evidence download failed. Please retry.");
            return response.json();
          })
        : await api(`/runs/${run.id}/export`);
      download(JSON.stringify(result, null, 2), `difftrial-${run.id}.json`);
    } catch (e) {
      setNotice((e as Error).message);
    }
  }
  return (
    <article className="run-detail">
      <div className="breadcrumb">
        <a href="#runs">Runs</a>
        <span>/</span>
        <code>{run.id.slice(0, 8)}</code>
      </div>
      <div className="heading-row">
        <div>
          <p className="eyebrow">
            {run.task.profile} · {run.task.source.kind} · v
            {run.task.source.version.slice(0, 12)}
          </p>
          <h1>{run.task.title}</h1>
          <p className="lead">{run.task.issue}</p>
        </div>
        <div className="actions">
          <button className="primary" onClick={exportEvidence}>
            Download evidence
          </button>
          {!__DEMO__ && !terminal(run.status) && (
            <button onClick={cancel}>Cancel run</button>
          )}
        </div>
      </div>
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {run.error && (
        <p className="error" role="alert">
          {run.error}
        </p>
      )}
      <dl className="run-facts">
        <div>
          <dt>Execution</dt>
          <dd>{label(run.status)}</dd>
        </div>
        <div>
          <dt>Test outcome</dt>
          <dd className={run.outcome === "fixed" ? "success" : ""}>
            {label(run.outcome)}
          </dd>
        </div>
        <div>
          <dt>Reviewer verdict</dt>
          <dd>{label(run.verdict)}</dd>
        </div>
        <div>
          <dt>Provider / model</dt>
          <dd>
            {run.provider.kind}
            <small>{run.provider.model}</small>
          </dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{duration(run)}</dd>
        </div>
      </dl>
      <p className="evidence-note">
        {run.task.source.kind === "github"
          ? "Existing tests do not establish that this imported issue is resolved."
          : "A fix means the protected regression and existing tests passed after a failing baseline. Review is a separate judgment."}
      </p>
      <div className="workbench-heading">
        <h2>Repair evidence</h2>
        {run.attempts.length > 0 && (
          <label className="inline-label">
            Attempt
            <select
              aria-label="Attempt"
              value={attemptIndex}
              onChange={(e) => setAttemptIndex(Number(e.target.value))}
            >
              {run.attempts.map((a, i) => (
                <option key={a.number} value={i}>
                  {a.number} of {run.attempts.length}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="pane-tabs" role="tablist" aria-label="Run evidence">
        {tabs.map((tab, i) => (
          <button
            key={tab}
            id={`tab-${tab}`}
            role="tab"
            aria-selected={pane === tab}
            aria-controls={`pane-${tab}`}
            tabIndex={pane === tab ? 0 : -1}
            onClick={() => setPane(tab)}
            onKeyDown={(e) => {
              if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) {
                e.preventDefault();
                const next =
                  e.key === "Home"
                    ? 0
                    : e.key === "End"
                      ? tabs.length - 1
                      : (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) %
                        tabs.length;
                setPane(tabs[next]);
                document.getElementById(`tab-${tabs[next]}`)?.focus();
              }
            }}
          >
            {label(tab)}
          </button>
        ))}
      </div>
      <div className="workbench">
        <section
          id="pane-patch"
          aria-labelledby="tab-patch"
          className={`pane patch-pane ${pane === "patch" ? "mobile-active" : ""}`}
        >
          <div className="section-heading">
            <h3>Proposed patch</h3>
            {attempt && (
              <button
                className="text-button"
                onClick={() =>
                  download(attempt.patch, `attempt-${attempt.number}.diff`)
                }
              >
                Download diff
              </button>
            )}
          </div>
          {attempt ? (
            <pre className="diff" aria-label="Unified code diff">
              {attempt.patch.split("\n").map((line, i) => (
                <span
                  key={i}
                  className={
                    line.startsWith("+") && !line.startsWith("+++")
                      ? "added"
                      : line.startsWith("-") && !line.startsWith("---")
                        ? "removed"
                        : line.startsWith("@@")
                          ? "hunk"
                          : ""
                  }
                >
                  {line || " "}
                  <br />
                </span>
              ))}
            </pre>
          ) : (
            <p className="empty-pane">No patch has been recorded.</p>
          )}
        </section>
        <section
          id="pane-evidence"
          aria-labelledby="tab-evidence"
          className={`pane ${pane === "evidence" ? "mobile-active" : ""}`}
        >
          <TestReport title="Baseline tests" report={run.baseline.tests} />
          <TestReport title="Patched tests" report={attempt?.reports.tests} />
          <section className="report">
            <h3>Static analysis</h3>
            <p>
              Baseline:{" "}
              {run.baseline.static
                ? `exit ${run.baseline.static.exit_code}`
                : "Not run"}{" "}
              · Patched:{" "}
              {attempt?.reports.static
                ? `exit ${attempt.reports.static.exit_code}`
                : "Not run"}
            </p>
            {attempt?.reports.static && (
              <details>
                <summary>Static analysis log</summary>
                <pre>{attempt.reports.static.log || "No findings."}</pre>
              </details>
            )}
          </section>
        </section>
        <section
          id="pane-review"
          aria-labelledby="tab-review"
          className={`pane ${pane === "review" ? "mobile-active" : ""}`}
        >
          <div className="section-heading">
            <h3>Review findings</h3>
            <span className="mono">{run.rubric_version}</span>
          </div>
          <p>
            {attempt?.review.summary ||
              "The reviewer has not submitted a verdict."}
          </p>
          <ul className="findings">
            {attempt?.review.findings?.map((f, i) => (
              <li key={i}>
                <span className="mono">
                  {f.rule} · {f.severity}
                </span>
                <p>{f.message}</p>
                {f.path && <code>{f.path}</code>}
              </li>
            ))}
          </ul>
        </section>
        <section
          id="pane-activity"
          aria-labelledby="tab-activity"
          className={`pane ${pane === "activity" ? "mobile-active" : ""}`}
        >
          <div className="section-heading">
            <h3>Agent activity</h3>
            <span>{__DEMO__ ? "Recorded" : label(run.stage)}</span>
          </div>
          <ol className="activity">
            {run.events.map((e) => (
              <li key={e.id}>
                <span className="event-number">
                  {String(e.id).padStart(2, "0")}
                </span>
                <div>
                  <strong>
                    {e.payload.role || e.payload.tool || label(e.kind)}
                  </strong>
                  <p>
                    {e.payload.summary ||
                      e.payload.message ||
                      e.payload.name ||
                      (e.payload.exit_code !== undefined
                        ? `Process exited with code ${e.payload.exit_code}.`
                        : "Event recorded.")}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>
      <details className="provenance">
        <summary>Source provenance and execution limits</summary>
        <dl>
          <dt>Source</dt>
          <dd>
            {run.task.source.repository ? (
              <a
                href={`${run.task.source.repository}/tree/${run.task.source.commit}`}
                target="_blank"
                rel="noreferrer"
              >
                {run.task.source.repository} at{" "}
                {run.task.source.commit?.slice(0, 12)}
              </a>
            ) : (
              run.task.source.benchmark_id
            )}
          </dd>
          <dt>Source SHA-256</dt>
          <dd>
            <code>{run.task.source.tree_sha256}</code>
          </dd>
          <dt>Limits</dt>
          <dd>
            {run.limits.attempts} attempts · {run.limits.run_seconds}s deadline
            · {run.limits.command_seconds}s per command · {run.limits.memory_mb}{" "}
            MiB · {run.limits.cpus} CPU
          </dd>
          <dt>Usage</dt>
          <dd>
            {run.usage.input_tokens ?? "Unavailable"} input tokens ·{" "}
            {run.usage.output_tokens ?? "Unavailable"} output tokens
            {run.cost_usd !== undefined && ` · $${run.cost_usd.toFixed(4)}`}
          </dd>
          <dt>Recorded</dt>
          <dd>
            {date(run.created)} · {run.prompt_version}
          </dd>
        </dl>
      </details>
    </article>
  );
}

function LocalTools({
  benchmarks,
  onCreated,
}: {
  benchmarks: Benchmark[];
  onCreated: (id: string) => void;
}) {
  const [provider, setProvider] = useState<Provider>(initialProvider);
  const [source, setSource] = useState("benchmark");
  const [benchmark, setBenchmark] = useState(benchmarks[0]?.id ?? "");
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("HEAD");
  const [profile, setProfile] = useState("python");
  const [issue, setIssue] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [docker, setDocker] = useState("Checking Docker…");
  const [deadline, setDeadline] = useState(900);
  const [commandLimit, setCommandLimit] = useState(300);
  useEffect(() => {
    api<{ config: Provider }>("/providers")
      .then((r) => setProvider(r.config))
      .catch((e) => setNotice(e.message));
    api<{ docker: { message: string } }>("/health")
      .then((r) => setDocker(r.docker.message))
      .catch((e) => setDocker(e.message));
  }, []);
  function setKind(kind: Provider["kind"]) {
    setProvider({
      ...provider,
      kind,
      transport: kind === "ollama" ? "ollama" : "responses",
      endpoint: kind === "ollama" ? "http://127.0.0.1:11434" : "",
      model: "",
      key_env:
        kind === "ollama"
          ? ""
          : kind === "codexlb"
            ? "CODEX_LB_API_KEY"
            : "OPENAI_API_KEY",
    });
    setModels([]);
  }
  async function operation(fn: () => Promise<void>) {
    setBusy(true);
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    await operation(async () => {
      const task = await api<{ id: string }>(
        "/tasks",
        "POST",
        source === "benchmark"
          ? { benchmark_id: benchmark }
          : { github_url: url, ref, issue, profile },
      );
      const run = await api<Run>("/runs", "POST", {
        task_id: task.id,
        provider,
        limits: { run_seconds: deadline, command_seconds: commandLimit },
      });
      onCreated(run.id);
    });
  }
  return (
    <>
      <div className="heading-row">
        <div>
          <p className="eyebrow">Local workspace</p>
          <h1>Create a repair run</h1>
          <p className="lead">
            Choose a task and a provider. The worker records every attempt.
          </p>
        </div>
      </div>
      <p className="notice">{docker}</p>
      <form onSubmit={submit} className="local-form">
        <section>
          <h2>Task source</h2>
          <label>
            Source
            <select aria-label="Source" value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="benchmark">Original benchmark</option>
              <option value="github">Public GitHub repository</option>
            </select>
          </label>
          {source === "benchmark" ? (
            <>
              <label>
                Benchmark
                <select
                  aria-label="Benchmark"
                  value={benchmark}
                  onChange={(e) => setBenchmark(e.target.value)}
                >
                  {benchmarks.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.profile} / {b.title}
                    </option>
                  ))}
                </select>
              </label>
              <p className="muted">
                {benchmarks.find((b) => b.id === benchmark)?.issue}
              </p>
            </>
          ) : (
            <>
              <label>
                Repository URL
                <input
                  type="url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://github.com/owner/repository"
                />
              </label>
              <label>
                Branch, tag or commit
                <input
                  required
                  value={ref}
                  onChange={(e) => setRef(e.target.value)}
                />
              </label>
              <label>
                Runner profile
                <select
                  aria-label="Runner profile"
                  value={profile}
                  onChange={(e) => setProfile(e.target.value)}
                >
                  <option value="python">Python / pytest</option>
                  <option value="typescript">TypeScript / Vitest</option>
                </select>
              </label>
              <label>
                Issue description
                <textarea
                  required
                  value={issue}
                  onChange={(e) => setIssue(e.target.value)}
                  rows={5}
                />
              </label>
              <p className="muted">
                Use src/ and tests/. Python needs requirements.txt and
                requirements.lock with hashes; TypeScript needs package.json and
                package-lock.json. Maximum repository size: 20 MiB.
              </p>
            </>
          )}
          <details>
            <summary>Execution limits</summary>
            <label>
              Run deadline (seconds)
              <input
                type="number"
                min={30}
                max={3600}
                value={deadline}
                onChange={(e) => setDeadline(Number(e.target.value))}
              />
            </label>
            <label>
              Command timeout (seconds)
              <input
                type="number"
                min={5}
                max={900}
                value={commandLimit}
                onChange={(e) => setCommandLimit(Number(e.target.value))}
              />
            </label>
            <p>One active run and at most two patch attempts.</p>
          </details>
        </section>
        <section>
          <h2>Provider settings</h2>
          <label>
            Provider
            <select
              aria-label="Provider"
              value={provider.kind}
              onChange={(e) => setKind(e.target.value as Provider["kind"])}
            >
              <option value="codexlb">CodexLB</option>
              <option value="compatible">OpenAI-compatible API</option>
              <option value="ollama">Ollama</option>
            </select>
          </label>
          {provider.kind === "compatible" && (
            <label>
              Transport
              <select
                aria-label="Transport"
                value={provider.transport}
                onChange={(e) =>
                  setProvider({
                    ...provider,
                    transport: e.target.value as Provider["transport"],
                  })
                }
              >
                <option value="responses">Responses</option>
                <option value="chat">Chat Completions</option>
              </select>
            </label>
          )}
          <label>
            Endpoint
            <input
              type="url"
              required
              value={provider.endpoint}
              onChange={(e) =>
                setProvider({ ...provider, endpoint: e.target.value })
              }
            />
          </label>
          <label>
            Model
            {models.length ? (
              <select
                aria-label="Model"
                value={provider.model}
                onChange={(e) =>
                  setProvider({ ...provider, model: e.target.value })
                }
              >
                {models.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            ) : (
              <input
                required
                value={provider.model}
                onChange={(e) =>
                  setProvider({ ...provider, model: e.target.value })
                }
              />
            )}
          </label>
          {provider.kind === "ollama" && (
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                operation(async () => {
                  const result = await api<{ models: string[] }>(
                    "/providers/models",
                    "POST",
                    { ...provider, model: provider.model || "discovery" },
                  );
                  setModels(result.models);
                  if (result.models.length)
                    setProvider({ ...provider, model: result.models[0] });
                  setNotice(
                    result.models.length
                      ? "Installed models loaded."
                      : "No installed models. Run ollama pull with the model name locally.",
                  );
                })
              }
            >
              Load installed models
            </button>
          )}
          {provider.kind !== "ollama" && (
            <p className="muted">
              The key is read from <code>{provider.key_env}</code> in the
              backend environment. Credentials are never entered in this
              dashboard.
            </p>
          )}
          <details>
            <summary>Optional pricing</summary>
            <label>
              Input USD per million tokens
              <input
                type="number"
                min={0}
                step="any"
                value={provider.input_price_per_million ?? ""}
                onChange={(e) =>
                  setProvider({
                    ...provider,
                    input_price_per_million: e.target.value
                      ? Number(e.target.value)
                      : null,
                  })
                }
              />
            </label>
            <label>
              Output USD per million tokens
              <input
                type="number"
                min={0}
                step="any"
                value={provider.output_price_per_million ?? ""}
                onChange={(e) =>
                  setProvider({
                    ...provider,
                    output_price_per_million: e.target.value
                      ? Number(e.target.value)
                      : null,
                  })
                }
              />
            </label>
          </details>
          <div className="actions">
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                operation(async () => {
                  await api("/providers", "PUT", provider);
                  setNotice("Provider settings saved locally.");
                })
              }
            >
              Save settings
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                operation(async () => {
                  await api("/providers/check", "POST", provider);
                  setNotice(
                    "Connection verified with an actual generation request.",
                  );
                })
              }
            >
              Check connection
            </button>
          </div>
          <p className="muted">
            A connection check makes one small model request and may incur
            provider usage.
          </p>
        </section>
        <div className="form-submit">
          {notice && (
            <p role="status" className="notice">
              {notice}
            </p>
          )}
          <button className="primary" disabled={busy}>
            {busy ? "Working…" : "Queue repair run"}
          </button>
        </div>
      </form>
    </>
  );
}

export default function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [route, setRoute] = useState(location.hash.slice(1) || "runs");
  const [theme, setTheme] = useState(
    () => localStorage.getItem("difftrial-theme") || "light",
  );
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [language, setLanguage] = useState("all");
  const loadingRef = useRef(false);
  const refresh = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    try {
      const result = await loadDashboard();
      setData(result);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      loadingRef.current = false;
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const change = () => setRoute(location.hash.slice(1) || "runs");
    addEventListener("hashchange", change);
    return () => removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("difftrial-theme", theme);
  }, [theme]);
  const active = data?.runs.find((r) => !terminal(r.status));
  useEffect(() => {
    if (__DEMO__ || !active) return;
    const events = new EventSource(`/api/v1/runs/${active.id}/events`);
    events.addEventListener("progress", refresh);
    events.addEventListener("done", () => {
      events.close();
      void refresh();
    });
    const timer = setInterval(refresh, 5000);
    return () => {
      events.close();
      clearInterval(timer);
    };
  }, [active?.id, refresh]);
  const run = data?.runs.find((r) => route === `runs/${r.id}`);
  const runs =
    data?.runs.filter(
      (r) =>
        (filter === "all" || r.outcome === filter || r.status === filter) &&
        `${r.task.title} ${r.provider.model} ${r.id}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    ) ?? [];
  const nav = route.split("/")[0];
  const comparisons =
    selected.length && data
      ? compareSelected(data.runs.filter((r) => selected.includes(r.id)))
      : (data?.comparisons ?? []);
  return (
    <div className="app">
      <a className="skip-link" href="#main" onClick={e => {
        e.preventDefault();
        document.getElementById("main")?.focus();
        document.getElementById("main")?.scrollIntoView();
      }}>
        Skip to content
      </a>
      <header className="app-header">
        <a className="wordmark" href="#runs">
          DiffTrial<span>Code repair workbench</span>
        </a>
        <nav aria-label="Main navigation">
          {["runs", "compare", "benchmarks"].map((n) => (
            <a
              key={n}
              href={`#${n}`}
              aria-current={nav === n ? "page" : undefined}
            >
              {n[0].toUpperCase() + n.slice(1)}
            </a>
          ))}
        </nav>
        <div className="header-end">
          <span className="mode">
            {__DEMO__ ? "Recorded demo" : "Local workspace"}
          </span>
          <button
            className="theme-toggle"
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
          >
            {theme === "light" ? "Dark" : "Light"}
          </button>
        </div>
      </header>
      {__DEMO__ && (
        <div className="recorded-banner">
          Recorded runs, inspectable evidence. This demo does not execute code
          or accept credentials.
        </div>
      )}
      <main id="main" tabIndex={-1}>
        {loading ? (
          <State title="Loading run evidence">
            <p role="status">Fetching recorded results…</p>
          </State>
        ) : error ? (
          <State title="Results are unavailable">
            <p role="alert">{error}</p>
            <button
              onClick={() => {
                setLoading(true);
                void refresh();
              }}
            >
              Retry loading
            </button>
          </State>
        ) : (
          data && (
            <>
              {run ? (
                <RunDetail run={run} reload={refresh} />
              ) : route.startsWith("runs/") ? (
                <State title="Run not found">
                  <p>This run is not in the selected evidence set.</p>
                  <a href="#runs">Return to runs</a>
                </State>
              ) : nav === "new" && !__DEMO__ ? (
                <LocalTools
                  benchmarks={data.benchmarks}
                  onCreated={(id) => {
                    void refresh();
                    location.hash = `runs/${id}`;
                  }}
                />
              ) : nav === "runs" ? (
                <>
                  <div className="heading-row">
                    <div>
                      <p className="eyebrow">Repair ledger</p>
                      <h1>Every patch has a record.</h1>
                      <p className="lead">
                        Inspect the proposal, the test evidence, and the review
                        that followed.
                      </p>
                    </div>
                    {!__DEMO__ && (
                      <a href="#new" className="button primary">
                        Create repair run
                      </a>
                    )}
                  </div>
                  <div className="overview">
                    <div>
                      <span>Recorded runs</span>
                      <strong>{data.runs.length}</strong>
                    </div>
                    <div>
                      <span>Completed executions</span>
                      <strong>
                        {
                          data.runs.filter((r) => r.status === "completed")
                            .length
                        }
                      </strong>
                    </div>
                    <div>
                      <span>Infrastructure errors</span>
                      <strong>
                        {
                          data.runs.filter((r) =>
                            ["infrastructure_error", "interrupted"].includes(
                              r.status,
                            ),
                          ).length
                        }
                      </strong>
                    </div>
                    <p>
                      Execution status, test outcome, and review verdict are
                      independent. Open a run to see the evidence.
                    </p>
                  </div>
                  <div className="toolbar">
                    <label className="search">
                      Find a run
                      <input
                        type="search"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Task, model or run ID"
                      />
                    </label>
                    <label>
                      Outcome
                      <select
                        aria-label="Outcome"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                      >
                        <option value="all">All outcomes</option>
                        <option value="fixed">Fixed</option>
                        <option value="failing">Failing</option>
                        <option value="regressed">Regressed</option>
                        <option value="infrastructure_error">
                          Infrastructure error
                        </option>
                        <option value="interrupted">Interrupted</option>
                        <option value="cancelled">Cancelled</option>
                      </select>
                    </label>
                    <button onClick={() => void refresh()}>
                      Refresh results
                    </button>
                    {selected.length > 0 && (
                      <a className="button" href="#compare">
                        Compare {selected.length} selected
                      </a>
                    )}
                  </div>
                  {runs.length ? (
                    <div className="run-table">
                      <div className="table-heading">
                        <span>Select</span>
                        <span>Task / source</span>
                        <span>Provider / model</span>
                        <span>Execution</span>
                        <span>Tests / review</span>
                        <span>Duration</span>
                      </div>
                      {runs.map((r) => (
                        <div className="run-row" key={r.id}>
                          <label className="selection">
                            <input
                              type="checkbox"
                              aria-label={`Select ${r.task.title} ${r.id.slice(0, 8)}`}
                              checked={selected.includes(r.id)}
                              onChange={(e) =>
                                setSelected(
                                  e.target.checked
                                    ? [...selected, r.id]
                                    : selected.filter((id) => id !== r.id),
                                )
                              }
                            />
                          </label>
                          <div>
                            <a href={`#runs/${r.id}`} className="run-link">
                              {r.task.title}
                            </a>
                            <small>
                              {r.task.profile} · <code>{r.id.slice(0, 8)}</code>
                            </small>
                          </div>
                          <div>
                            {r.provider.kind}
                            <small>{r.provider.model}</small>
                          </div>
                          <span>{label(r.status)}</span>
                          <div>
                            <span
                              className={
                                r.outcome === "fixed"
                                  ? "success"
                                  : ["failing", "regressed"].includes(r.outcome)
                                    ? "failure"
                                    : ""
                              }
                            >
                              {label(r.outcome)}
                            </span>
                            <small>Review: {label(r.verdict)}</small>
                          </div>
                          <span className="mono">{duration(r)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <State
                      title={
                        data.runs.length
                          ? "No matching runs"
                          : "No runs recorded yet"
                      }
                    >
                      <p>
                        {data.runs.length
                          ? "Change the search or outcome filter to see other runs."
                          : __DEMO__
                            ? "Only verified, explicitly selected runs are published here. The benchmark catalog is available now."
                            : "Choose an original benchmark or import a supported public repository to begin."}
                      </p>
                      {data.runs.length ? (
                        <button
                          onClick={() => {
                            setSearch("");
                            setFilter("all");
                          }}
                        >
                          Clear filters
                        </button>
                      ) : (
                        <a href={__DEMO__ ? "#benchmarks" : "#new"}>
                          {__DEMO__ ? "View benchmarks" : "Create repair run"}
                        </a>
                      )}
                    </State>
                  )}
                </>
              ) : nav === "benchmarks" ? (
                <>
                  <div className="heading-row">
                    <div>
                      <p className="eyebrow">Original task suite</p>
                      <h1>Small faults. Specific contracts.</h1>
                      <p className="lead">
                        Twelve versioned tasks cover boundaries, ordering, and
                        data integrity. Each keeps its regression tests
                        protected.
                      </p>
                    </div>
                  </div>
                  <div className="toolbar">
                    <label>
                      Language
                      <select
                        aria-label="Language"
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                      >
                        <option value="all">Both languages</option>
                        <option value="python">Python / pytest</option>
                        <option value="typescript">TypeScript / Vitest</option>
                      </select>
                    </label>
                    <span className="muted">
                      6 Python · 6 TypeScript · suite v1.0.0
                    </span>
                  </div>
                  <div className="benchmark-list">
                    {data.benchmarks
                      .filter(
                        (b) => language === "all" || b.profile === language,
                      )
                      .map((b, i) => (
                        <article key={b.id}>
                          <span className="benchmark-number">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <div>
                            <p className="eyebrow">
                              {b.profile} · {b.id}
                            </p>
                            <h2>{b.title}</h2>
                            <p>{b.issue}</p>
                          </div>
                          <span className="mono">v{b.version}</span>
                        </article>
                      ))}
                  </div>
                  <aside className="method-note">
                    <h2>How results are counted</h2>
                    <p>
                      A benchmark fix requires a failing baseline, passing
                      protected regression tests, no lost existing passes, and
                      passing static checks. Comparisons use the same source
                      hash, prompt, rubric, and limits. Infrastructure errors
                      are counted separately. This suite is small and
                      purpose-built; its results do not estimate general coding
                      ability.
                    </p>
                  </aside>
                </>
              ) : nav === "compare" ? (
                <>
                  <div className="heading-row">
                    <div>
                      <p className="eyebrow">Matched conditions</p>
                      <h1>Compare the evidence.</h1>
                      <p className="lead">
                        Providers are grouped by identical task versions and
                        execution limits. Every rate includes its denominator.
                      </p>
                    </div>
                  </div>
                  {selected.length > 0 && (
                    <div className="notice">
                      {selected.length} selected runs.{" "}
                      <button
                        className="text-button"
                        onClick={() => setSelected([])}
                      >
                        Clear selection
                      </button>
                      <div className="comparison-runs">
                        {data.runs
                          .filter((r) => selected.includes(r.id))
                          .map((r) => (
                            <a key={r.id} href={`#runs/${r.id}`}>
                              {r.task.title} · {r.id.slice(0, 8)}
                            </a>
                          ))}
                      </div>
                    </div>
                  )}
                  {comparisons.length ? (
                    <>
                      <p className="muted">
                        {selected.length
                          ? "Cohorts below include only the selected runs."
                          : "Cohorts below include all recorded runs."}
                      </p>
                      <div className="comparison-list">
                        {comparisons.map((c, i) => (
                          <article key={`${c.cohort}-${i}`}>
                            <div>
                              <p className="eyebrow">
                                Cohort {c.cohort} · v{c.version.slice(0, 12)}
                              </p>
                              <h2>{c.task}</h2>
                              <p>
                                {c.provider} / {c.model}
                              </p>
                            </div>
                            <dl>
                              <div>
                                <dt>Observed fixes</dt>
                                <dd>
                                  {c.fixed} / {c.eligible}
                                  <small>
                                    {c.fix_rate === null
                                      ? "No eligible repairs"
                                      : `${Math.round(c.fix_rate * 100)}% of eligible repairs`}
                                  </small>
                                </dd>
                              </div>
                              <div>
                                <dt>Regressed runs</dt>
                                <dd>
                                  {c.regressions} / {c.total}
                                </dd>
                              </div>
                              <div>
                                <dt>Infrastructure errors</dt>
                                <dd>
                                  {c.infrastructure_errors} / {c.total}
                                </dd>
                              </div>
                              <div>
                                <dt>Duration</dt>
                                <dd>{Math.round(c.duration_seconds)}s total</dd>
                              </div>
                              <div>
                                <dt>Token usage</dt>
                                <dd>
                                  {c.usage_available_runs
                                    ? `${c.input_tokens} in / ${c.output_tokens} out`
                                    : "Unavailable"}
                                  <small>
                                    {c.usage_available_runs} / {c.total} runs
                                    reporting usage
                                  </small>
                                </dd>
                              </div>
                            </dl>
                          </article>
                        ))}
                      </div>
                    </>
                  ) : (
                    <State title="No comparable evidence yet">
                      <p>
                        Complete runs on the same benchmark version and limits
                        to populate provider comparisons.
                      </p>
                      <a href="#runs">View runs</a>
                    </State>
                  )}
                  <aside className="method-note">
                    <h2>Denominators matter</h2>
                    <p>
                      Fix-rate denominators include completed benchmark runs
                      with a failing baseline. Cancelled, interrupted,
                      infrastructure-error runs and imported repositories are
                      excluded. Review acceptance is not part of the test fix
                      rate. Compare failures and exclusions alongside the rate.
                    </p>
                  </aside>
                </>
              ) : (
                <State title="Page not found">
                  <a href="#runs">Return to runs</a>
                </State>
              )}
            </>
          )
        )}
      </main>
      <footer>
        <span>DiffTrial · Evidence before conclusions.</span>
        <a
          href="https://github.com/acespades10/Agentic-Code-Review-Sandbox"
          target="_blank"
          rel="noreferrer"
        >
          Source & setup
        </a>
        <span>
          {__DEMO__
            ? "Recorded activity · No live execution"
            : "Local execution · Environment-held credentials"}
        </span>
      </footer>
    </div>
  );
}
