# Model Evaluation Framework

Shared, trustworthy metrics so Uday, Akash and Gopi's models can be compared
on the same basis instead of each computing accuracy their own way.

## 1. What I built

- `src/metrics.py` - MAPE, RMSE, precision/recall/f1, confusion matrix,
  accuracy, and anomaly-detection metrics (precision, recall, f1,
  specificity, false positive rate, balanced accuracy). Labels must be
  `{0, 1}` -- sklearn-style `{-1, 1}` anomaly labels (IsolationForest, LOF)
  raise a clear error rather than being silently miscounted; remap them to
  `{0, 1}` before calling.
- `src/baseline.py` - naive "tomorrow = today" forecast + comparison, with
  explicit tie-handling
- `src/splits.py` - chronological train/test split and a general k-fold
  walk-forward splitter (no shuffling, ever)
- `src/report.py` - side-by-side comparison table, handles missing metrics
  gracefully (shows N/A instead of crashing)
- `src/leaderboard.py` - ranks multiple models by a chosen metric; refuses
  to rank if models report incompatible, non-numeric, or NaN metrics
- `src/significance.py` - paired t-test across folds, to check whether one
  model's improvement over another is statistically real or just noise
- `src/guardrails.py` - automated leakage checks: train/test overlap
  detection, chronological-order enforcement, suspicious-accuracy warnings
  -- encodes the project's core safety discipline as reusable, automatic
  checks
- `src/backtest.py` - reusable backtesting harness: simulates many
  historical "pretend it's date X, predict forward" points for any
  forecaster (plugged in via a simple function contract), not just a
  single train/test split
- `src/report_html.py` - generates a complete, self-contained HTML
  evaluation report (metrics table, baseline comparison, significance
  results, embedded charts) -- the artifact a non-technical stakeholder can
  open and read
- `src/leaderboard_service.py` - a live FastAPI `/leaderboard` HTTP
  endpoint, wrapping the existing leaderboard logic so any external caller
  (not just Python code importing this package) can rank models and get
  the same refusal behavior for incompatible metrics
- `compare.py` - standalone CLI: `python compare.py --results results.json`
- `tests/test_metrics.py` - 122 tests covering all of the above, including
  edge cases and error/refusal paths

Note: MAPE excludes rows where the actual value is 0, since division by zero
is undefined there.

## 2. How to run it

```bash
cd ml-services/eval-framework
pip install -r requirements.txt
python run_demo.py
pytest
```

For the Prophet-based leaderboard/significance demo specifically, also
install the demo-only dependency (kept separate since it's a heavy
compiler-toolchain dependency not needed by the core framework or test
suite themselves):

```bash
pip install -r requirements-demo.txt
python run_leaderboard.py
```

## 3. If I had another day

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

## How any model in this pod could use this

Say Uday has a trained Prophet model and wants to compare it against naive,
using this framework, without me touching his code. Since this isn't
packaged for pip-style installation yet, the practical way to use it today
is to run from inside `eval-framework/`, or add it to the path explicitly:

```python
# In Uday's own script, run from inside ml-services/eval-framework/,
# or with the path added explicitly:
import sys
sys.path.append("/path/to/ml-services/eval-framework")

from src.metrics import mape, rmse
from src.splits import walk_forward_split

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
model code -- anyone can plug in their own predictions. (A proper installable
package, e.g. via a `pyproject.toml`, would make the import cleaner -- noted
as a possible future improvement.)

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

- **`src/metrics.py`** - `anomaly_metrics()`: precision, recall, f1,
  specificity, false positive rate, and balanced accuracy, specifically for
  anomaly detection where the normal class vastly outnumbers the anomaly
  class (plain accuracy is misleading there -- `accuracy()` exists
  separately, with an explicit warning about this). `confusion_matrix()`
  validates labels are `{0, 1}` and raises a clear error on sklearn-style
  `{-1, 1}` labels instead of silently miscounting.
- **`src/leaderboard.py`** - `generate_leaderboard()` and `print_leaderboard()`.
  Ranks any number of models by a chosen metric, best first. Refuses to rank
  and gives a clear error if any model is missing that metric, reports a
  non-numeric or NaN value for it, or if fewer than 2 models are comparable.
  Direction (higher/lower is better) is inferred automatically from a shared
  `HIGHER_IS_BETTER_METRICS` set in `metrics.py`, so it can never drift out
  of sync with `report.py`.
- **`src/significance.py`** - `paired_significance_test()`. Runs a paired
  t-test across matching folds for two models, and reports whether one
  model's apparent improvement over another is statistically real or could
  be explained by random noise. Handles the zero-variance edge case
  (identical differences across every fold) explicitly using a tolerance
  check, since scipy's t-test becomes numerically unstable there.

### Why this matters

A single metric on a single split can be misleading. This adds two more
layers of honesty: the leaderboard refuses to compare apples to oranges, and
the significance test refuses to call a small improvement "better" unless
the data actually backs that up.

### How to run the leaderboard/significance demo

```bash
cd ml-services/eval-framework
pip install -r requirements.txt -r requirements-demo.txt
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
from src.leaderboard import print_leaderboard

results = {"naive": {"mape": 6.80}, "some_model": {"precision": 0.9}}
print_leaderboard(results, "mape")
# Cannot generate leaderboard: Cannot rank: metric 'mape' is missing for
# model(s) ['some_model']. All models must report the same metric to be
# ranked together.
```

### Example: confusion_matrix rejecting sklearn-style anomaly labels

```python
from src.metrics import confusion_matrix

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
pip install -r requirements.txt
uvicorn src.leaderboard_service:app --reload --port 8000
```

Then, from any other terminal or tool:

```bash
curl -X POST http://127.0.0.1:8000/leaderboard \
  -H "Content-Type: application/json" \
  -d '{"results": {"naive": {"mape": 6.80}, "prophet": {"mape": 3.20}}, "metric": "mape"}'
```

Incompatible metrics are refused with HTTP 422 and the same clear error
message as the Python-level function.

### How to generate an HTML report

```python
from src.report_html import save_html_report
from src.significance import paired_significance_test

results = {"naive": {"mape": 6.22}, "prophet": {"mape": 8.78}}
sig_result = paired_significance_test(naive_mapes, prophet_mapes)
save_html_report(results, "evaluation_report.html", significance_result=sig_result)
```

### How to use the backtesting harness

```python
from src.backtest import backtest

def my_forecast_fn(train_df, horizon):
    # any forecaster -- naive, Prophet, your own model
    ...
    return predictions

results = backtest(df, "date", "y", my_forecast_fn, horizon=1, min_train_size=30)
```

### How to use the guardrails

```python
from src.guardrails import run_all_guardrails, LeakageError

try:
    result = run_all_guardrails(train, test, "date", score=model_accuracy)
    if result["warnings"]:
        print(result["warnings"])
except LeakageError as e:
    print("Hard failure:", e)
```

## Experiment Tracking Dashboard, Regression Detection, and Fairness Testing

### What's included

- **`src/mlflow_dashboard.py`** - `get_all_runs()` reads every finished
  MLflow run for an experiment, across every model owner who has logged to
  it, via an explicit `MlflowClient` (never mutates global tracking state),
  and paginates automatically past MLflow's default 1000-run page limit.
  `summarize_dashboard()` groups those runs by owner and model, showing each
  pair's latest score and total run count. Runs missing the owner/model tag
  are grouped under an explicit `"untagged"` bucket and counted -- never
  silently dropped or allowed to crash the sort -- since real Pod 2 runs
  won't all have these tags from day one.
- **`src/regression_detection.py`** - `detect_regression()` compares a
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
- **`src/fairness.py`** - `evaluate_by_slice()` computes a metric
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
` min_absolute_gap`, since rmse's real scale is data-dependent and has no
  safe universal default the way mape and accuracy do.

### Why this matters

An aggregate metric and a single retrain comparison can both hide real
problems: a model can look fine overall while failing badly on one
subgroup, and a retrain can quietly get worse without anyone noticing
unless the comparison is automatic. These three modules close that gap --
they don't replace the existing metrics, they add visibility on top of them.

### How to run the demo

```bash
cd ml-services/eval-framework
pip install -r requirements.txt -r requirements-demo.txt
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
`detect_regression()` -- works unchanged once runs are logged there;
they were built against a generic MLflow client, not this demo's local
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
from src.mlflow_dashboard import get_all_runs, summarize_dashboard
from src.regression_detection import detect_regression

runs = get_all_runs("pod2-forecasting", tracking_uri="http://<shared-mlflow-host>:5000")

dashboard = summarize_dashboard(runs, metric="mape")
for (owner, model), info in dashboard["by_owner_model"].items():
    print(f"{owner}/{model}: {info['latest_score']:.4f} ({info['n_runs']} runs)")

# After a weekly retrain, check nobody's model got worse:
result = detect_regression(runs, owner="uday", model_name="prophet", metric="mape")
if result["regressed"]:
    print(result["message"])  # alert / block promotion / etc.
```