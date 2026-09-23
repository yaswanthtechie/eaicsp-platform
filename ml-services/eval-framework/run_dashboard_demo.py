"""
Demo: logs real MLflow runs for two different model owners (simulating
Uday's Prophet forecaster and Kalyani's naive baseline, tagged accordingly),
then demonstrates the dashboard reading across owners and regression
detection catching a deliberately-worse retrain.

Uses a local MLflow tracking store (./mlruns) for this demo. Pointed at the
pod's real shared MLflow server, the same code reads everyone's actual
logged runs -- nothing in mlflow_dashboard.py or regression_detection.py
is specific to this local demo.
"""
import mlflow
import pandas as pd

from src.mlflow_dashboard import get_all_runs, summarize_dashboard
from src.regression_detection import detect_regression
from src.metrics import mape
from src.baseline import naive_forecast

EXPERIMENT = "pod2-forecasting-demo"
mlflow.set_experiment(EXPERIMENT)

URL = "https://raw.githubusercontent.com/facebook/prophet/main/examples/example_retail_sales.csv"
df = pd.read_csv(URL)
df.columns = ["date", "y"]
actual = df["y"].tolist()[-30:]

# --- Kalyani's naive baseline: two runs, identical method -- genuinely NO
#     regression, not just "small noise" that could accidentally flag ---
naive_preds = naive_forecast(actual)
naive_mape = mape(actual, naive_preds)

with mlflow.start_run(run_name="naive-v1"):
    mlflow.set_tags({"owner": "kalyani", "model_name": "naive"})
    mlflow.log_metric("mape", naive_mape)

with mlflow.start_run(run_name="naive-v2"):
    mlflow.set_tags({"owner": "kalyani", "model_name": "naive"})
    mlflow.log_metric("mape", naive_mape)  # identical -- proves no false positive

# --- Uday's Prophet: two runs, DELIBERATELY worse second retrain ---
prophet_preds_v1 = [actual[0]] * len(actual)  # stand-in "good" run
with mlflow.start_run(run_name="prophet-v1"):
    mlflow.set_tags({"owner": "uday", "model_name": "prophet"})
    mlflow.log_metric("mape", mape(actual, prophet_preds_v1))

prophet_preds_v2 = [actual[0] * 1.5] * len(actual)  # deliberately bad retrain
with mlflow.start_run(run_name="prophet-v2-bad-retrain"):
    mlflow.set_tags({"owner": "uday", "model_name": "prophet"})
    mlflow.log_metric("mape", mape(actual, prophet_preds_v2))

print("\n=== Runs logged. Reading dashboard across both owners ===\n")

runs = get_all_runs(EXPERIMENT)
dashboard = summarize_dashboard(runs, metric="mape")

print(f"Owners in this experiment: {dashboard['owners']}")
print(f"Models in this experiment: {dashboard['models']}")
for (owner, model), info in dashboard["by_owner_model"].items():
    print(f"  {owner} / {model}: latest MAPE={info['latest_score']:.4f}, {info['n_runs']} run(s) logged")

print("\n=== Checking for regressions ===\n")

kalyani_check = detect_regression(runs, owner="kalyani", model_name="naive", metric="mape")
print("Kalyani/naive:", kalyani_check["message"])

uday_check = detect_regression(runs, owner="uday", model_name="prophet", metric="mape")
print("Uday/prophet:", uday_check["message"])

print("\n=== Fairness/slice check (synthetic per-warehouse example) ===\n")

from src.fairness import evaluate_by_slice

slice_df = pd.DataFrame({
    "warehouse": ["A"] * 10 + ["B"] * 10 + ["C"] * 10,
    "actual": [100] * 30,
    "predicted": [105] * 10 + [98] * 10 + [150] * 10,  # C genuinely bad
})
fairness_result = evaluate_by_slice(slice_df, "warehouse", "actual", "predicted", "mape")
print(fairness_result["summary"])