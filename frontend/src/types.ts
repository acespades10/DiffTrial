declare global {
  const __DEMO__: boolean;
}

export type Provider = {
  kind: "codexlb" | "compatible" | "ollama";
  transport: "responses" | "chat" | "ollama";
  endpoint: string;
  model: string;
  key_env: string;
  input_price_per_million?: number | null;
  output_price_per_million?: number | null;
};
export type Benchmark = {
  id: string;
  title: string;
  profile: string;
  issue: string;
  version: string;
  protected_tests: string[];
};
export type Report = {
  exit_code: number;
  report_valid: boolean;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  log: string;
  cases: { name: string; status: string }[];
};
export type Reports = { tests?: Report; static?: Report; regressions?: number };
export type Attempt = {
  number: number;
  patch: string;
  reports: Reports;
  review: {
    summary?: string;
    verdict?: string;
    findings?: {
      rule: string;
      severity: string;
      message: string;
      path?: string;
    }[];
  };
};
export type Run = {
  protocol?: string;
  id: string;
  status: string;
  stage: string;
  outcome: string;
  verdict: string;
  created: number;
  started: number | null;
  finished: number | null;
  error?: string;
  provider: Pick<Provider, "kind" | "model" | "transport">;
  prompt_version: string;
  rubric_version: string;
  limits: {
    attempts: number;
    run_seconds: number;
    command_seconds: number;
    memory_mb: number;
    cpus: number;
  };
  usage: { input_tokens?: number; output_tokens?: number };
  cost_usd?: number;
  task: {
    id: string;
    title: string;
    issue: string;
    profile: string;
    source: {
      kind: string;
      version: string;
      benchmark_id?: string;
      repository?: string;
      commit?: string;
      tree_sha256?: string;
      evaluation: string;
    };
  };
  baseline: Reports;
  attempts: Attempt[];
  events: {
    id: number;
    kind: string;
    created: number;
    payload: {
      role?: string;
      summary?: string;
      tool?: string;
      message?: string;
      name?: string;
      exit_code?: number;
      log?: string;
    };
  }[];
};
export type Comparison = {
  cohort: string;
  task: string;
  version: string;
  provider: string;
  model: string;
  total: number;
  eligible: number;
  fixed: number;
  fix_rate: number | null;
  regressions: number;
  infrastructure_errors: number;
  failed_repairs: number;
  duration_seconds: number;
  input_tokens: number;
  output_tokens: number;
  usage_available_runs: number;
};
export type DashboardData = {
  runs: Run[];
  benchmarks: Benchmark[];
  comparisons: Comparison[];
};
