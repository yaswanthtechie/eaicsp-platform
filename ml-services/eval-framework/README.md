# Model Evaluation Framework

Shared, trustworthy metrics so Uday, Akash and Gopi's models can be compared
on the same basis instead of each computing accuracy their own way.

## 1. What I built

- `src/metrics.py` - MAPE, RMSE, precision/recall/f1, confusion matrix, and
  anomaly-detection metrics (recall, specificity, false positive rate,
  balanced accuracy). Labels must be `{0, 1}` -- sklearn-style `{-1, 1}`
  anomaly labels (IsolationForest, LOF) raise a clear error rather than
  being silently miscounted; remap them to `{0, 1}` before calling.
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
- `compare.py` - standalone CLI: `python compare.py --results results.json`
- `tests/test_metrics.py` - 36 tests covering all of the above, including
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
- Add a bootstrap-based alternative to the paired t-test in `significance.py`,
  for cases with very few folds where a t-test's normality assumption is shakier.
- Extend `leaderboard.py` to rank across multiple metrics at once (currently
  one metric per call), with a way to weight them if they disagree.
- Add MLflow logging so every leaderboard/significance run is automatically
  recorded with a permanent history, instead of only existing in the
  terminal or a manually-saved output file.

## 4. What I got stuck on

- My first `matplotlib` install got cancelled mid-way, and leftover terminal text
  afterward confused PowerShell into throwing errors - turned out harmless, just
  needed a clean re-run.
- Wasn't sure whether to add `__init__.py` since the doc didn't mention it - needed
  it for clean imports between my own files (`baseline.py` using `metrics.py`).
- Missed that the repo's root `.gitignore` has a `*.csv` rule, which silently
  excluded my data file from the first push - fixed by reading the CSV straight
  from the source URL instead of a local file.
- A review caught a scipy import with no declared dependency file, which
  errors out all tests on a clean install - fixed with `requirements.txt`.
- My first significance-test demo used a synthetic "toy model" instead of a
  real second model - fixed by training an actual Prophet model myself,
  compared against naive on the same real dataset and folds.
- A later review caught that `confusion_matrix` silently miscounted
  sklearn-style `{-1, 1}` anomaly labels instead of erroring - fixed by
  validating labels explicitly and raising a clear error with remap guidance.

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

This keeps the evaluation logic completely decoupled from any one person's
model code -- anyone can plug in their own predictions. (A proper installable
package, e.g. via a `pyproject.toml`, would make the import cleaner -- noted
as a possible future improvement.)

## Design note: why compare.py and leaderboard.py handle missing metrics differently

`compare.py` / `report.py` shows `N/A` for any metric a model didn't report,
and continues printing the rest of the table. This is intentional: it's a
broad, exploratory tool -- useful to see everything you have, even if some
cells are incomplete.

`leaderboard.py` refuses outright and raises a clear error if any model is
missing the metric being ranked on, reports a non-numeric value, or reports
NaN. This is also intentional: a ranking is a definitive claim ("X is better
than Y"), and that claim isn't trustworthy if the models weren't even
measured on the same thing, or if a value is meaningless. Silently skipping
a model or showing a partial ranking would be misleading.

In short: `compare.py` optimizes for visibility, `leaderboard.py` optimizes
for trustworthiness. Both are deliberate, not an oversight.

## Full Metrics Suite, Leaderboard, and Significance Testing

### What's included

- **`src/metrics.py`** - `anomaly_metrics()`: recall, specificity, false
  positive rate, and balanced accuracy, specifically for anomaly detection
  where the normal class vastly outnumbers the anomaly class (plain accuracy
  is misleading there). `confusion_matrix()` validates labels are `{0, 1}`
  and raises a clear error on sklearn-style `{-1, 1}` labels instead of
  silently miscounting.
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