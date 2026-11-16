# Staged evidence recording

The normal local worker runs all stages on one machine. When Docker is unavailable locally, the opt-in `Record Docker evidence` workflow supports a transparent split-host demonstration without uploading model credentials.

1. Dispatch the workflow's `baseline` phase. It measures Docker baseline tests and static analysis for `py-intervals` and `ts-versions`, with source hashes and a GitHub Actions run ID.
2. Download `baselines.json` into an ignored local directory. Run `python scripts/record_evidence.py generate --input .local/baselines.json --output evidence/candidates.json`. The local CodexLB adapter produces real planner, implementer and validator outputs using those measured baselines. The script also adds one explicitly labeled comment-only negative control.
3. Review and commit the candidates. They contain no credentials or endpoint. Dispatch `evaluate`. It checks source hashes, measures a fresh baseline, applies the constrained proposals, runs offline Docker tests and static checks, and exports `evaluations.json`. No model call happens in CI.
4. Download the evaluations. Run `python scripts/record_evidence.py review --input .local/evaluations.json --output frontend/public/demo`. The local model reviews actual measured results. The negative control gets a clearly identified deterministic assessment, not a fabricated model review.
5. Inspect the selected JSON and checksums, then publish the static demo. Event timestamps preserve generation on the local machine and execution on CI; a provenance event names both CI runs.

The staged recorder intentionally permits only the two named original benchmark tasks. It is not a hosted arbitrary-repository execution service. Routine CI uses deterministic fixtures, not the live provider.
