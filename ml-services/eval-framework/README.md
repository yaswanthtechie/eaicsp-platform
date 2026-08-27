# Model Evaluation Framework

Shared, trustworthy metrics so Uday, Akash and Gopi's models can be compared
on the same basis instead of each computing accuracy their own way.

## 1. What I built

- `src/metrics.py` - MAPE, RMSE, and precision/recall/f1
- `src/baseline.py` - naive "tomorrow = today" forecast + comparison
- `src/splits.py` - chronological train/test split (no shuffling)
- `src/report.py` - side-by-side comparison table
- `tests/test_metrics.py` - hand-computed checks for each formula

Note: MAPE excludes rows where the actual value is 0, since division by zero
is undefined there.

## 2. How to run it

```bash
cd ml-services/eval-framework
pip install pandas numpy scikit-learn pytest
python run_demo.py
pytest
```

## 3. If I had another day

- Test this against a real model (not just naive), once one is ready.
- Fix the winner logic in `report.py` so it also works for precision/recall/f1
  (right now it only works correctly for MAPE/RMSE).
- Handle ties properly in `compare_to_baseline` (right now a tie always goes to naive).


## 4. What I got stuck on

- My first `matplotlib` install got cancelled mid-way, and leftover terminal text
  afterward confused PowerShell into throwing errors - turned out harmless, just
  needed a clean re-run.
- Wasn't sure whether to add `__init__.py` since the doc didn't mention it - needed
  it for clean imports between my own files (`baseline.py` using `metrics.py`).
- Missed that the repo's root `.gitignore` has a `*.csv` rule, which silently
  excluded my data file from the first push - fixed by reading the CSV straight
  from the source URL instead of a local file.

## How any model in this pod could use this

Say Uday has a trained Prophet model and wants to compare it against naive,
using this framework, without me touching his code:

```python
# In Uday's own script:
from eval_framework.src.metrics import mape, rmse
from eval_framework.src.splits import walk_forward_split

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
python compare.py --results uday_results.json
```

This keeps the evaluation logic completely decoupled from any one person's
model code -- anyone can plug in their own predictions.


## Round 3: Full Metrics Suite, Leaderboard, and Significance Testing

### What's new this round

- **`src/metrics.py`** — added `anomaly_metrics()`: recall, specificity, false positive
  rate, and balanced accuracy, specifically for anomaly detection where the normal
  class vastly outnumbers the anomaly class (plain accuracy is misleading there).
- **`src/leaderboard.py`** — `generate_leaderboard()` and `print_leaderboard()`.
  Ranks any number of models by a chosen metric, best first. Refuses to rank
  and gives a clear error if any model is missing that metric, or if fewer
  than 2 models are comparable -- it will never force a fake ranking across
  incompatible metrics.
- **`src/significance.py`** — `paired_significance_test()`. Runs a paired
  t-test across matching folds (e.g., 5 walk-forward folds) for two models,
  and reports whether one model's apparent improvement over another is
  statistically real or could be explained by random noise.

### Why this matters

A single metric on a single split can be misleading (see the framework's own
design: MAPE and RMSE can disagree, and one split can just be lucky). This
round adds two more layers of honesty: the leaderboard refuses to compare
apples to oranges, and the significance test refuses to call a small
improvement "better" unless the data actually backs that up.

### How to run the Round 3 demo

```bash
cd ml-services/eval-framework
pip install scipy
python run_leaderboard.py
```

This runs a 5-fold walk-forward comparison on the real retail sales dataset,
prints a leaderboard, and reports whether the difference between the two
result sets is statistically significant.

**Known limitation:** no second real model is wired into eval-framework yet
(explicitly out of scope through Round 2 and this round). The demo uses a
"toy model" (a deliberately worse naive variant) purely to prove the
leaderboard and significance-testing machinery work correctly on real
project data -- not as a meaningful model comparison. When a real second
model becomes available, swap it in using the same pattern.

### Example: leaderboard refusing an invalid comparison

```python
from src.leaderboard import print_leaderboard

results = {"naive": {"mape": 6.80}, "some_model": {"precision": 0.9}}
print_leaderboard(results, "mape")
# Cannot generate leaderboard: Cannot rank: metric 'mape' is missing for
# model(s) ['some_model']. All models must report the same metric to be
# ranked together.
```