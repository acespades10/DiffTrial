# Benchmark methodology v1

Twelve original tasks, six per language, each have a small implementation, existing test coverage and a separate protected regression test. The catalog defines the issue contract. Source hashes include code, tests, and locked dependencies. The known-good repair fixtures are held under `tests/fixtures/`; production agents receive source files but not fixtures or protected test files.

Python tasks cover touching intervals, zero weights, partial pagination, exact expiration, Unicode casefolding and zero ledger amounts. TypeScript tasks cover numeric version segments, zero queue capacity, UTC date boundaries, duplicate record replacement, partial chunks and partial moving-average windows.

## Counts

- **Observed fix:** baseline has actual failing tests; patched tests have a successful daemon exit, a valid nonempty report, every case passes, no baseline pass is lost, and static analysis exits zero.
- **Regression:** a previously passing test name is missing or no longer passing.
- **Eligible denominator:** completed original benchmark runs and rejected-patch runs with a failing baseline. Invalid proposals count as failed repairs, so they cannot inflate the observed fix rate. Imported repositories, cancelled runs, interrupted runs, provider failures and other infrastructure errors are excluded.
- **Failed repair:** a completed attempt without a fixed/passing outcome, or an invalid patch rejected by the boundary. Infrastructure failure is counted separately.
- **Duration:** runner execution interval per run, summed within a cohort. Staged experiments report execution duration separately from recorded model-call timestamps; these durations must not be compared directly with end-to-end local runs.
- **Usage:** only provider-reported tokens; the count of runs reporting usage is shown. Cost appears only when both input/output prices are explicitly configured and usage is present.

Cohorts require identical source provenance, task version, limits, prompt, rubric and recording protocol. Staged CI and local worker records never share a cohort. Provider and model form the compared groups. Selected-run filtering preserves these boundaries. Repeated attempts belong to one run and do not inflate its denominator.

These tasks are deliberately small boundary/data-integrity bugs. A small observed rate on this suite is not a general software-engineering score. The first public evidence set is a demonstration, not a statistically powered provider comparison. A deliberately incomplete negative control is labeled as a control and kept in its own group; it is not a model failure.

Any change to task contract, tests, code or dependencies requires a new task version before further comparative measurement. Keep all original evidence bundles so results remain auditable.
