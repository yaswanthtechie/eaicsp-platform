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