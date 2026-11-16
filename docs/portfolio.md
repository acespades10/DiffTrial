# Portfolio wording

## Project description

Built DiffTrial, a local agentic code repair workbench using React, TypeScript, FastAPI and SQLite. A durable background worker coordinates planner, implementer, validator and reviewer roles, with constrained source edits and disposable Docker checks. The dashboard separates execution status, measured test outcomes and review verdicts, and exports inspectable evidence to a read-only GitHub Pages demo.

## Resume bullets

- Implemented a four-role repair workflow with a persistent job queue, cancellation, worker recovery, reconnectable progress events and versioned evidence exports.
- Created 12 original Python and TypeScript benchmarks with protected regression tests; verified all 12 known repairs and container isolation checks in Linux CI.
- Recorded two real CodexLB repair examples with failing baselines and passing patched checks, plus a deliberately unsuccessful negative control; published sanitized diffs, reports, review findings and artifact checksums.

## Evidence boundaries

The two model examples are selected demonstrations, not a statistically meaningful fix-rate estimate or provider ranking. Their Docker execution ran on GitHub Actions and their model calls ran locally. The negative control was intentionally authored and is not a model failure. Routine CI uses deterministic adapters and makes no paid model calls.

CodexLB Responses was checked live. Other compatible endpoints and Ollama have transport tests but remain unverified against a live configured service. Docker was verified on Linux CI, not on this Windows development machine. No claim is made about production adoption, general model performance, independent security certification, or large-scale patch evaluation.
