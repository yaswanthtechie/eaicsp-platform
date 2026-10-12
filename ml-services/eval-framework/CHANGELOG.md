# Changelog

All notable changes to `eval-framework` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Versioning: [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-02

First installable release. The public API is frozen as documented in the README
("Public API"): breaking changes to it require a MAJOR version bump (MINOR while
below 1.0.0, and always noted here).

### Added
- Installable package: `pip install -e .` (import name `eval_framework`, `src/` layout,
  `pyproject.toml`). Core install needs only numpy and pandas; the extras
  `stats`, `report`, `mlflow`, `service`, `dev` and `all` add the rest.
- Anomaly detection evaluation (`eval_framework.anomaly`): `threshold_metrics`,
  `pr_auc`, `precision_at_k`, `find_events`, `event_scores`.
- ETA / interval regression evaluation (`eval_framework.eta`): `mae_by_horizon`,
  `interval_coverage` (with mean interval width).
- `mae()` in `eval_framework.metrics`.
- Registry: `TARGET_METRICS` for metrics best close to a target (`interval_coverage`);
  new higher-is-better metrics (`pr_auc`, `precision_at_k`, `event_*`) and
  lower-is-better metrics (`mae`, `mean_interval_width`).
- `eval-gate` CLI (`eval_framework.gate`): compares a candidate MLflow run to a
  baseline run and exits 0 (pass), 1 (regression beyond margin) or 2 (no verdict).
  Read-only; fails closed.

### Changed
- Import path changed from `src.*` to `eval_framework.*`. Update any code that
  imported `src`.
- `pytest.ini` no longer adds the project root to the path; tests run against the
  installed package (`pip install -e ".[dev]"` first).

### Earlier work (pre-packaging, unversioned)
- Core metrics, baseline and splitting, reporting (console and HTML), leaderboard
  and its FastAPI service, significance testing, backtesting, guardrails,
  MLflow dashboard, regression detection, and fairness slicing.