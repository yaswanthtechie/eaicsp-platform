# Model Evaluation Framework

Shared, trustworthy metrics so Uday, Akash and Gopi's models can be compared
on the same basis instead of each computing accuracy their own way.

Current version: **0.1.0** (see `CHANGELOG.md`). Installable package, import
name `eval_framework`.

## Install

```bash
cd ml-services/eval-framework
pip install -e .              # core: numpy + pandas only
pip install -e ".[all]"       # + scipy, matplotlib, mlflow, fastapi/uvicorn
pip install -e ".[all,dev]"   # + pytest, httpx (needed to run the tests)
```

Extras: `stats` (scipy), `report` (matplotlib), `mlflow`, `service` (fastapi,
uvicorn), `dev` (pytest, httpx), `all` (stats + report + mlflow + service).

Python 3.10 or newer is declared. So far it has only been tested on Python 3.12
on Windows.

To use it from another folder in the monorepo (for example the ETA Prediction
or Anomaly Detection projects), install it into that project's environment:

```bash
pip install -e "../eval-framework[all]"
```

`requirements.txt` still pins the exact versions used for development and the
demos; `pyproject.toml` declares the minimum versions the library needs.

## Public API (frozen at 0.1.0)

Public names will not change without a version bump and a `CHANGELOG.md` entry.
Everything else is internal and may change at any time.

**Top level (`from eval_framework import ...`, works on a core install):**

| Area | Names |
|---|---|
| Metrics | `mape`, `rmse`, `mae`, `confusion_matrix`, `precision_recall`, `accuracy`, `anomaly_metrics` |
| Metric registry | `HIGHER_IS_BETTER_METRICS`, `LOWER_IS_BETTER_METRICS`, `TARGET_METRICS`, `KNOWN_METRICS`, `SUSPICIOUS_THRESHOLDS` |
| Anomaly detection | `threshold_metrics`, `pr_auc`, `precision_at_k`, `find_events`, `event_scores` |
| ETA / intervals | `mae_by_horizon`, `interval_coverage` |
| Baseline and splits | `naive_forecast`, `compare_to_baseline`, `time_based_split`, `walk_forward_split` |
| Guardrails | `LeakageError`, `check_no_train_test_overlap`, `check_chronological_order`, `check_suspicious_accuracy`, `run_all_guardrails` |
| Ranking, reporting, slices, regression | `generate_leaderboard`, `print_leaderboard`, `compare_models`, `evaluate_by_slice`, `detect_regression` |
| Version | `__version__` |

**Submodule imports (some need an extra installed):**

| Import | Needs |
|---|---|
| `from eval_framework.backtest import backtest` | core |
| `from eval_framework.significance import paired_significance_test, wilcoxon_significance_test` | `stats` |
| `from eval_framework.report_html import generate_html_report, save_html_report` | `report` |
| `from eval_framework.mlflow_dashboard import get_all_runs, summarize_dashboard` | `mlflow` |
| `from eval_framework.gate import run_gate, main, GateError, EXIT_PASS, EXIT_REGRESSION, EXIT_NO_VERDICT` | `mlflow` (to read runs) |
| `eval_framework.leaderboard_service:app` (FastAPI app) | `service` |

`backtest` is deliberately not re-exported at the top level: a function named
`backtest` would replace the module of the same name on the package. The modules
that need scipy, matplotlib, mlflow or fastapi are also not imported at the top
level, so a core install imports without any of them.

**Internal (do not import):** anything starting with an underscore (for example
`eval_framework._validation`), the helper functions in `gate.py` other than
those listed above, and the pydantic models in `leaderboard_service.py`.

**Metric registry rule:** a metric name outside `KNOWN_METRICS` is unknown, and
callers must state its direction explicitly. `TARGET_METRICS` (for example
`interval_coverage`) are best when close to a target value, so they are
deliberately not in `KNOWN_METRICS` and always need explicit handling.

## 1. What I built

- `src/eval_framework/metrics.py` - MAPE, RMSE, MAE, precision/recall/f1, confusion
  matrix, accuracy, and anomaly-detection metrics (precision, recall, f1,
  specificity, false positive rate, balanced accuracy). Also holds the central
  metric registry. Labels must be `{0, 1}` -- sklearn-style `{-1, 1}` anomaly
  labels (IsolationForest, LOF) raise a clear error rather than being silently
  miscounted; remap them to `{0, 1}` before calling.
- `src/eval_framework/anomaly.py` - threshold precision/recall/F1, PR-AUC,
  precision@k and event-level scoring for anomaly detectors
- `src/eval_framework/eta.py` - MAE by prediction horizon and prediction-interval
  coverage (with mean interval width) for ETA-style models
- `src/eval_framework/gate.py` - the `eval-gate` command: compares a candidate
  MLflow run to a baseline run and exits non-zero on a regression
- `src/eval_framework/_validation.py` - internal input checks shared by the
  metric modules (not public API)
- `src/eval_framework/baseline.py` - naive "tomorrow = today" forecast + comparison, with
  explicit tie-handling
- `src/eval_framework/splits.py` - chronological train/test split and a general k-fold
  walk-forward splitter (no shuffling, ever)
- `src/eval_framework/report.py` - side-by-side comparison table, handles missing metrics
  gracefully (shows N/A instead of crashing)
- `src/eval_framework/leaderboard.py` - ranks multiple models by a chosen metric; refuses
  to rank if models report incompatible, non-numeric, or NaN metrics
- `src/eval_framework/significance.py` - paired t-test and Wilcoxon signed-rank test
  across folds, to check whether one model's improvement over another is
  statistically real or just noise
- `src/eval_framework/guardrails.py` - automated leakage checks: train/test overlap
  detection, chronological-order enforcement, suspicious-accuracy warnings
  -- encodes the project's core safety discipline as reusable, automatic
  checks
- `src/eval_framework/backtest.py` - reusable backtesting harness: simulates many
  historical "pretend it's date X, predict forward" points for any
  forecaster (plugged in via a simple function contract), not just a
  single train/test split
- `src/eval_framework/report_html.py` - generates a complete, self-contained HTML
  evaluation report (metrics table, baseline comparison, significance
  results, embedded charts) -- the artifact a non-technical stakeholder can
  open and read
- `src/eval_framework/leaderboard_service.py` - a live FastAPI `/leaderboard` HTTP
  endpoint, wrapping the existing leaderboard logic so any external caller
  (not just Python code importing this package) can rank models and get
  the same refusal behavior for incompatible metrics
- `src/eval_framework/mlflow_dashboard.py`, `regression_detection.py`, `fairness.py` -
  MLflow run reading, retrain regression detection and per-slice checks
  (described below)
- `compare.py` - standalone CLI: `python compare.py --results results.json`
- `tests/` - 219 tests: `test_metrics.py` (122, the original modules),
  `test_anomaly_eta.py` (43), `test_gate.py` (49) and `test_public_api.py` (5),
  including edge cases and error/refusal paths

Note: MAPE excludes rows where the actual value is 0, since division by zero
is undefined there.

## 2. How to run it

```bash
cd ml-services/eval-framework
pip install -e ".[all,dev]"
pytest
python run_demo.py
```

The tests run against the installed package (there is no path hack in
`pytest.ini`), so the install step must come first. Without it, pytest fails
with `ModuleNotFoundError: No module named 'eval_framework'`.

For the Prophet-based demos (`run_demo.py`, `run_leaderboard.py`,
`run_dashboard_demo.py`), also install the demo-only dependency (kept separate
since it's a heavy compiler-toolchain dependency not needed by the core
framework or test suite themselves):

```bash
pip install -r requirements-demo.txt
python run_leaderboard.py
```

## 3. If I had another day

- Wire `eval-gate` into a GitHub Actions check so a worse model actually blocks
  a merge (the command exists and is tested; nothing calls it in CI yet).
- Test on Python 3.10 and 3.11 and on Linux, since only Python 3.12 on Windows
  has been verified so far.
- Wire the framework into a real teammate's model output for real (still
  deliberately deferred so far -- the leaderboard demo builds its own
  Prophet fit rather than importing anyone else's code).
- Add MLflow logging so every leaderboard/significance run is automatically
  recorded with a permanent history, instead of only existing in the
  terminal or a manually-saved output file.

## 4. What I got stuck on

- My first `matplotlib` install got cancelled mid-way, and leftover terminal
  text afterward confused PowerShell into throwing errors - turned out
  harmless, just needed a clean re-run.
- Wasn't sure whether to add `__init__.py` since the doc didn't mention it -
  needed it for clean imports between my own files (`baseline.py` using
  `metrics.py`).
- Missed that the repo's root `.gitignore` has a `*.csv` rule, which
  silently excluded my data file from the first push - fixed by reading the
  CSV straight from the source URL instead of a local file.
- A review caught a scipy import with no declared dependency file, which
  errors out all tests on a clean install - fixed with `requirements.txt`.
- My first significance-test demo used a synthetic "toy model" instead of a
  real second model - fixed by training an actual Prophet model myself,
  compared against naive on the same real dataset and folds.
- A later review caught that `confusion_matrix` silently miscounted
  sklearn-style `{-1, 1}` anomaly labels instead of erroring - fixed by
  validating labels explicitly and raising a clear error with remap
  guidance.
- Packaging: the code lived in a folder literally named `src`, which would have
  installed as a package called `src` and collided with any other project using
  the same name. Renamed to `src/eval_framework/` and rewrote 47 imports.
- After removing `pythonpath = .` from `pytest.ini`, plain `pytest` on my dev
  machine failed with `ModuleNotFoundError`. That was the intended safety
  check: tests must pass against the installed package, not against whatever
  folder I happened to run them from.
- I assumed `run_leaderboard.py` would run without Prophet; it imports Prophet
  on line 2, so it needs `requirements-demo.txt` like `run_demo.py`.

## Using this on other models (ETA Prediction, Anomaly Detection, forecasting)

Say Uday has a trained Prophet model and wants to compare it against naive,
using this framework, without me touching his code. After installing the
package (see Install above), in his own script:

```python
from eval_framework import mape, rmse, walk_forward_split

folds = walk_forward_split(uday_df, "date", n_splits=5)
for train, test in folds:
    prophet_model.fit(train)
    preds = prophet_model.predict(test)
    print(mape(test["y"], preds), rmse(test["y"], preds))
```

Or, without touching Python at all -- just dump results into a JSON file and
run the standalone CLI:

```json
{"prophet": {"mape": 3.2, "rmse": 20500}, "xgboost": {"mape": 4.1, "rmse": 22100}}
```

```bash
cd ml-services/eval-framework
python compare.py --results uday_results.json
```

Or, without touching Python or this repo at all -- send results to the
running leaderboard service over HTTP (see below).

This keeps the evaluation logic completely decoupled from any one person's
model code -- anyone can plug in their own predictions.

## Anomaly Detection and ETA evaluation

All examples below use tiny synthetic data with answers that can be checked by
hand; the same cases are in `tests/test_anomaly_eta.py`.

### Anomaly detection (`eval_framework.anomaly`)

- **`threshold_metrics(y_true, scores, threshold)`** - precision/recall/F1 after
  flagging every point with `score >= threshold`. The threshold is a required
  argument, so nobody reports "the" F1 of a detector without saying where it
  was cut.
- **`pr_auc(y_true, scores)`** - area under the precision-recall curve. Needs no
  threshold and, unlike ROC-AUC, is not flattered by rare anomalies. Tied
  scores are grouped, so the result never depends on row order. Raises if
  there are no positive labels.
- **`precision_at_k(y_true, scores, k)`** - the share of true anomalies among the
  `k` highest-scored points (the alerts an on-call person can actually review).
  If tied scores straddle the k-th position it raises unless you pass
  `on_tie="first"`.
- **`find_events(labels)`** and **`event_scores(y_true, y_pred, tolerance=0)`** -
  event-level scoring. One anomaly lasting 10 steps is one event, not 10
  points. A true event counts as detected if any predicted run overlaps it
  (widened by `tolerance` time steps on each side). A predicted run that
  overlaps no true event is one false-alarm event. Ratios that are undefined
  (no predicted events, or no true events) are returned as `None`, never
  as a made-up 0.

```python
from eval_framework import threshold_metrics, pr_auc, precision_at_k, event_scores

y = [1, 0, 1, 0]
s = [0.9, 0.8, 0.7, 0.1]
threshold_metrics(y, s, 0.75)   # precision 0.5, recall 0.5, f1 0.5
pr_auc(y, s)                    # 5/6 = 0.8333...

precision_at_k([1, 0, 1, 0, 0], [0.9, 0.8, 0.7, 0.2, 0.1], 3)   # 2/3

true = [0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0]   # events at steps 1-4 and 8-9
pred = [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0]   # runs at step 2 and step 6
event_scores(true, pred)                       # event_recall 0.5, event_precision 0.5
event_scores(true, pred, tolerance=2)          # event_recall 1.0, event_precision 1.0
```

Labels must be exactly 0 or 1 and in chronological order with evenly spaced
steps; scores must be finite. Empty, NaN, infinite or mismatched-length input
raises a `ValueError`.

### ETA / interval regression (`eval_framework.eta`)

- **`mae(actual, predicted)`** (in `metrics`) - mean absolute error, in the units
  of the target.
- **`mae_by_horizon(y_true, y_pred, horizons, bins=None)`** - overall MAE plus
  MAE per prediction horizon (exact value, or per bucket if `bins` is given),
  with the row count `n` for each so thin buckets are visible. Horizons
  outside `bins` raise instead of being silently dropped.
- **`interval_coverage(y_true, lower, upper, nominal=None)`** - the share of true
  values inside `[lower, upper]` (inclusive), always returned together with the
  mean interval width, because coverage alone can be gamed with absurdly wide
  intervals. Inverted intervals (`lower > upper`) raise. If `nominal` is given
  (for example 0.9), `coverage_gap` is `coverage - nominal`.

```python
from eval_framework import mae_by_horizon, interval_coverage

mae_by_horizon([10, 10, 10, 10], [11, 9, 13, 7], [1, 1, 2, 2])
# overall_mae 2.0; horizon 1 -> mae 1.0 (n=2); horizon 2 -> mae 3.0 (n=2)

interval_coverage([1, 2, 3, 4, 5], [0, 3, 2, 5, 4], [2, 4, 4, 6, 6], nominal=0.9)
# interval_coverage 0.6, mean_interval_width 1.6, coverage_gap -0.3
```

`interval_coverage` is a "closer to a target" metric, not higher-is-better or
lower-is-better, so it lives in `TARGET_METRICS` (see Public API).

## eval-gate: an evaluation gate for CI

```bash
eval-gate --candidate <run_id> --baseline <run_id> --metric mae --max-regression 2% --tracking-uri sqlite:///mlflow.db
```

What it does:

- Reads the final logged value of `--metric` from each MLflow run and fails when
  the candidate is worse than the baseline by more than `--max-regression`.
- `--max-regression` is relative to the baseline and must end in `%`. A bare
  `2` is rejected, because it could mean 2% or 200%. A candidate exactly on the
  margin passes; an improvement always passes.
- Direction (higher or lower is better) comes from the shared metric registry.
  Metrics outside the registry need `--higher-is-better` or `--lower-is-better`.
  Target-style metrics such as `interval_coverage` are refused, because the gate
  has no target to compare against.
- A tracking URI is required (`--tracking-uri` or the `MLFLOW_TRACKING_URI`
  environment variable). A missing sqlite database file is refused, so a typo
  cannot make MLflow silently create an empty database.
- Read-only: it only reads runs and never logs, tags or modifies anything.
- Only `FINISHED` runs are accepted, and a run cannot be compared with itself.

Exit codes, the only thing CI reads:

| Code | Meaning |
|---|---|
| 0 | PASS: candidate is within the allowed margin |
| 1 | FAIL: candidate is worse than the baseline beyond the margin |
| 2 | NO VERDICT: bad arguments, missing run or metric, NaN or infinite value, unreadable MLflow, or any unexpected error |

The gate fails closed: it never passes when it could not actually check, and an
unexpected crash is reported as 2 (not Python's default 1, which would look like
a regression). It is not yet wired into GitHub Actions.

## Design note: why compare.py and leaderboard.py handle missing metrics differently

`compare.py` / `report.py` shows `N/A` for any metric a model didn't report,
and continues printing the rest of the table. This is intentional: it's a
broad, exploratory tool -- useful to see everything you have, even if some
cells are incomplete.

`leaderboard.py` (and the leaderboard service built on top of it) refuses
outright and raises a clear error if any model is missing the metric being
ranked on, reports a non-numeric value, or reports NaN. This is also
intentional: a ranking is a definitive claim ("X is better than Y"), and
that claim isn't trustworthy if the models weren't even measured on the
same thing, or if a value is meaningless. Silently skipping a model or
showing a partial ranking would be misleading.

In short: `compare.py` optimizes for visibility, `leaderboard.py` optimizes
for trustworthiness. Both are deliberate, not an oversight.

## Full Metrics Suite, Leaderboard, and Significance Testing

### What's included

- **`src/eval_framework/metrics.py`** - `anomaly_metrics()`: precision, recall, f1,
  specificity, false positive rate, and balanced accuracy, specifically for
  anomaly detection where the normal class vastly outnumbers the anomaly
  class (plain accuracy is misleading there -- `accuracy()` exists
  separately, with an explicit warning about this). `confusion_matrix()`
  validates labels are `{0, 1}` and raises a clear error on sklearn-style
  `{-1, 1}` labels instead of silently miscounting.
- **`src/eval_framework/leaderboard.py`** - `generate_leaderboard()` and `print_leaderboard()`.
  Ranks any number of models by a chosen metric, best first. Refuses to rank
  and gives a clear error if any model is missing that metric, reports a
  non-numeric or NaN value for it, or if fewer than 2 models are comparable.
  Direction (higher/lower is better) is inferred automatically from a shared
  `HIGHER_IS_BETTER_METRICS` set in `metrics.py`, so it can never drift out
  of sync with `report.py`.
- **`src/eval_framework/significance.py`** - `paired_significance_test()`. Runs a paired
  t-test across matching folds for two models, and reports whether one
  model's apparent improvement over another is statistically real or could
  be explained by random noise. Handles the zero-variance edge case
  (identical differences across every fold) explicitly using a tolerance
  check, since scipy's t-test becomes numerically unstable there.
  `wilcoxon_significance_test()` is the rank-based alternative; with 5 or
  fewer folds it cannot reach p < 0.05, which is a documented limitation.

### Why this matters

A single metric on a single split can be misleading. This adds two more
layers of honesty: the leaderboard refuses to compare apples to oranges, and
the significance test refuses to call a small improvement "better" unless
the data actually backs that up.

### How to run the leaderboard/significance demo

```bash
cd ml-services/eval-framework
pip install -e ".[all]" -r requirements-demo.txt
python run_leaderboard.py
```

This trains a naive baseline and a real Prophet model (default settings, no
tuning) on the same real retail sales dataset, across the same 5 walk-forward
folds, then runs the leaderboard and significance test on their actual MAPE
scores. Full captured output is saved in `demo_output.txt`.

Note: the Prophet model trained in this demo is not logged to MLflow --
eval-framework isn't a model-producing pod, so no model artifact needs
tracking here. If reproducibility of `demo_output.txt` specifically becomes
important, a minimal MLflow log of the run's parameters/metrics could be
added later.

**Real result (see `demo_output.txt` for the full run):** naive scored a
lower average MAPE than Prophet (6.22 vs 8.78) across the 5 folds, with
Prophet's error spiking badly on folds 4 and 5 (15.76 and 11.59 MAPE) likely
due to using Prophet with no seasonality/trend tuning. The leaderboard
correctly ranks naive first on raw average -- but the significance test
finds this difference is **not statistically significant** (p=0.327), since
Prophet's scores vary widely fold-to-fold. This is an honest, useful result:
it shows the significance test correctly refuses to declare naive the "real"
winner off 5 noisy folds, exactly the kind of premature conclusion this tool
is meant to prevent.

### Example: leaderboard refusing an invalid comparison

```python
from eval_framework import print_leaderboard

results = {"naive": {"mape": 6.80}, "some_model": {"precision": 0.9}}
print_leaderboard(results, "mape")
# Cannot generate leaderboard: Cannot rank: metric 'mape' is missing for
# model(s) ['some_model']. All models must report the same metric to be
# ranked together.
```

### Example: confusion_matrix rejecting sklearn-style anomaly labels

```python
from eval_framework import confusion_matrix

confusion_matrix([1, -1, 1, -1], [1, 1, -1, -1])
# ValueError: confusion_matrix: labels must be 0 or 1, got unexpected
# value(s) [-1]. If using sklearn-style anomaly labels ({-1, 1}), remap
# with e.g. [0 if v == 1 else 1 for v in labels] before calling this function.
```

## Metrics Rigor, Guardrails, Backtesting, HTML Reports, Leaderboard Service

### What's included

- **Consolidated `anomaly_metrics()`** now includes precision, recall, and
  f1 alongside specificity, false positive rate, and balanced accuracy --
  everything needed for class-imbalanced evaluation in one call. Added a
  standalone `accuracy()` with an explicit warning about its limitations
  under class imbalance.
- **`guardrails.py`** -- automated checks that catch the project's core
  safety rules without relying on a human reviewer: `check_no_train_test_overlap()`
  hard-fails on any row appearing in both sets, `check_chronological_order()`
  hard-fails if test dates aren't strictly after train dates, and
  `check_suspicious_accuracy()` soft-warns when a score is suspiciously high
  (a common sign of data leakage). `run_all_guardrails()` runs everything
  in one call.
- **`backtest.py`** -- a reusable harness that repeatedly simulates
  historical forecast points ("pretend it's date X, predict forward,
  compare to actual") for ANY forecaster, via a simple plug-in function
  contract `(train_data, horizon) -> predictions`. Integrates directly with
  existing metrics (e.g. feed backtest results straight into `mape()`).
  Supports multi-series data through `series_col`.
- **`report_html.py`** -- generates a single, self-contained HTML report
  (metrics table, baseline comparison, significance interpretation, embedded
  bar charts) from any model's results -- no external files needed, easy to
  share or email.
- **`leaderboard_service.py`** -- a live FastAPI service exposing
  `POST /leaderboard` and `GET /health`. Reuses the existing
  `generate_leaderboard()` logic, so external callers (not just Python code
  importing this package) get the exact same ranking and the exact same
  refusal behavior (HTTP 422) for incompatible metrics.

### How to run the leaderboard service

```bash
cd ml-services/eval-framework
pip install -e ".[service]"
uvicorn eval_framework.leaderboard_service:app --reload --port 8000
```

Then, from any other terminal or tool:

```bash
curl -X POST http://127.0.0.1:8000/leaderboard \
  -H "Content-Type: application/json" \
  -d '{"results": {"naive": {"mape": 6.80}, "prophet": {"mape": 3.20}}, "metric": "mape"}'
```

Interactive docs are at `http://127.0.0.1:8000/docs`. Incompatible metrics are
refused with HTTP 422 and the same clear error message as the Python-level
function.

### How to generate an HTML report

```python
from eval_framework.report_html import save_html_report
from eval_framework.significance import paired_significance_test

results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
sig_result = paired_significance_test(naive_mapes, prophet_mapes)
save_html_report(results, "evaluation_report.html", significance_result=sig_result)
```

### How to use the backtesting harness

```python
from eval_framework.backtest import backtest

def my_forecast_fn(train_df, horizon):
    # any forecaster -- naive, Prophet, your own model
    ...
    return predictions

results = backtest(df, "date", "y", my_forecast_fn, horizon=1, min_train_size=30)
```

### How to use the guardrails

```python
from eval_framework import run_all_guardrails, LeakageError

try:
    result = run_all_guardrails(train, test, "date", score=model_accuracy)
    if result["warnings"]:
        print(result["warnings"])
except LeakageError as e:
    print("Hard failure:", e)
```

## Experiment Tracking Dashboard, Regression Detection, and Fairness Testing

### What's included

- **`src/eval_framework/mlflow_dashboard.py`** - `get_all_runs()` reads every finished
  MLflow run for an experiment, across every model owner who has logged to
  it, via an explicit `MlflowClient` (never mutates global tracking state),
  and paginates automatically past MLflow's default 1000-run page limit.
  `summarize_dashboard()` groups those runs by owner and model, showing each
  pair's latest score and total run count. Runs missing the owner/model tag
  are grouped under an explicit `"untagged"` bucket and counted -- never
  silently dropped or allowed to crash the sort -- since real Pod 2 runs
  won't all have these tags from day one.
- **`src/eval_framework/regression_detection.py`** - `detect_regression()` compares a
  model's latest logged run against a baseline run and flags whether the
  latest one is genuinely worse. `baseline="previous"` (default) compares
  against the immediately prior run; `baseline="production"` compares
  against the most recent run tagged `stage="production"` instead, for
  comparing a new retrain against what's actually deployed rather than
  whatever happened to run most recently. Scores within floating-point
  tolerance are never flagged. The degradation threshold is computed on the
  baseline's absolute magnitude, so it works correctly for metrics that can
  be negative. A run missing the compared metric raises an error rather
  than silently reporting "no regression". Unrecognized metrics require an
  explicit direction, same rule as `leaderboard.py`.
  Comparing a run against itself when it's the only production-tagged run
  raises a clear error rather than trivially reporting no regression.
- **`src/eval_framework/fairness.py`** - `evaluate_by_slice()` computes a metric
  separately for each slice of a dataset (e.g. per warehouse, per category)
  and for the dataset overall, then flags any slice performing meaningfully
  worse than the aggregate. A model can look fine on average while quietly
  failing on one subgroup -- this surfaces that instead of hiding it behind
  a single aggregate number. A slice must clear both a relative threshold
  AND a minimum absolute gap before being flagged, so a tiny relative
  difference against a near-zero baseline (e.g. 20% of a 0.05 MAPE) doesn't
  falsely flag an objectively tiny slice. Slices smaller than
  `min_slice_size` are reported but never flagged, since too little data
  can't support a reliable conclusion.
  The absolute-gap floor can be set explicitly per call via
  `min_absolute_gap`, since rmse's real scale is data-dependent and has no
  safe universal default the way mape and accuracy do.

`detect_regression()` compares consecutive retrains of one model inside a
dashboard. `eval-gate` (above) is different: it compares two specific run ids,
and is meant to be a pass/fail step in CI.

### Why this matters

An aggregate metric and a single retrain comparison can both hide real
problems: a model can look fine overall while failing badly on one
subgroup, and a retrain can quietly get worse without anyone noticing
unless the comparison is automatic. These three modules close that gap --
they don't replace the existing metrics, they add visibility on top of them.

### How to run the demo

```bash
cd ml-services/eval-framework
pip install -e ".[all]" -r requirements-demo.txt
python run_dashboard_demo.py
```

This logs real MLflow runs for two simulated model owners (naive and
Prophet, tagged accordingly), reads them back through the dashboard,
demonstrates regression detection correctly finding no regression for an
unchanged model and correctly flagging a deliberately worse retrain, and
runs a synthetic per-warehouse fairness check.

**Real demo result:** naive's two runs are identical, correctly reported
as no regression. Prophet's second run was deliberately made much worse
(MAPE 9.71 -> 63.30), correctly flagged as a regression. The fairness
check correctly identified warehouse C as underperforming (predictions
~50% off) while warehouses A and B were within the normal range.

### Design note: contract-first integration (not wired this round)

`get_all_runs()` and `detect_regression()` are deliberately generic --
they operate on any MLflow experiment and any owner/model tags, not on
this demo's specific data. The intended integration, once wired:

```python
# Uday's, Gopi's, or Ajith's training scripts would log runs like this,
# tagged so this framework's dashboard can read and group them:
import mlflow

with mlflow.start_run():
    mlflow.set_tags({"owner": "uday", "model_name": "prophet"})
    mlflow.log_metric("mape", computed_mape)
    # ... their existing training/logging code, unchanged otherwise
```

No changes to anyone else's code are required this round -- only the two
tag keys (`owner`, `model_name`) and a consistent metric name are needed
for `get_all_runs()` / `summarize_dashboard()` / `detect_regression()` to
work against real, shared MLflow data. Actually wiring this against
Uday/Gopi/Ajith's live training runs is explicitly out of scope this round.

### Getting started (for anyone in the pod adopting this)

**1. Point at a shared MLflow tracking server (not this demo's local store)**

By default, this demo logs to a local `./mlruns` folder, which only your
own machine can read. For the dashboard to genuinely show everyone's runs,
MLflow needs to be pointed at wherever the pod's shared tracking server
lives (a URL like `http://<mlflow-host>:5000`, or a shared file path
reachable by everyone). Once that's set up pod-wide:

```python
import mlflow
mlflow.set_tracking_uri("http://<shared-mlflow-host>:5000")  # once, at the top of your training script
```

Everything else -- `get_all_runs()`, `summarize_dashboard()`,
`detect_regression()`, `eval-gate` -- works unchanged once runs are logged
there; they were built against a generic MLflow client, not this demo's local
store specifically.

**2. Tag conventions -- required for your runs to be readable by this framework**

Two tags are required on every run for the dashboard/regression tools to
find and group it correctly:

- `owner`: your name, lowercase, matching how you're referred to elsewhere
  in the pod's docs (e.g. `"uday"`, `"gopi"`, `"ajith"`) -- not a display
  name or email, just a consistent short identifier.
- `model_name`: the model this run belongs to (e.g. `"prophet"`,
  `"lstm"`, `"anomaly-isolation-forest"`) -- should stay the same across
  every retrain of that model, since `detect_regression()` compares runs
  sharing the same owner + model_name.

**3. Minimal example, once wired against real pod data**

```python
from eval_framework.mlflow_dashboard import get_all_runs, summarize_dashboard
from eval_framework import detect_regression

runs = get_all_runs("pod2-forecasting", tracking_uri="http://<shared-mlflow-host>:5000")

dashboard = summarize_dashboard(runs, metric="mape")
for (owner, model), info in dashboard["by_owner_model"].items():
    print(f"{owner}/{model}: {info['latest_score']:.4f} ({info['n_runs']} runs)")

# After a weekly retrain, check nobody's model got worse:
result = detect_regression(runs, owner="uday", model_name="prophet", metric="mape")
if result["regressed"]:
    print(result["message"])  # alert / block promotion / etc.
```