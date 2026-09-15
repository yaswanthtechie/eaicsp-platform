import pandas as pd
from prophet import Prophet
from src.metrics import mape
from src.splits import walk_forward_split
from src.baseline import naive_forecast
from src.leaderboard import print_leaderboard
from src.significance import paired_significance_test

URL = "https://raw.githubusercontent.com/facebook/prophet/main/examples/example_retail_sales.csv"
df = pd.read_csv(URL)
df.columns = ["date", "y"]
df["date"] = pd.to_datetime(df["date"])

folds = walk_forward_split(df, "date", n_splits=5)

naive_mapes = []
prophet_mapes = []

for i, (train, test) in enumerate(folds, start=1):
    actual = test["y"].tolist()

    # Naive baseline
    naive_preds = naive_forecast(actual)
    naive_mapes.append(mape(actual, naive_preds))

    # Real Prophet fit, trained on this fold's train data only (no leakage)
    prophet_train = train.rename(columns={"date": "ds", "y": "y"})[["ds", "y"]]
    model = Prophet()
    model.fit(prophet_train)

    future = test.rename(columns={"date": "ds"})[["ds"]]
    forecast = model.predict(future)
    prophet_preds = forecast["yhat"].tolist()
    prophet_mapes.append(mape(actual, prophet_preds))

    print(f"Fold {i}: naive MAPE={naive_mapes[-1]:.2f}, prophet MAPE={prophet_mapes[-1]:.2f}")

print()
print("Naive MAPE per fold:", [round(x, 2) for x in naive_mapes])
print("Prophet MAPE per fold:", [round(x, 2) for x in prophet_mapes])
print()

results = {
    "naive": {"mape": sum(naive_mapes) / len(naive_mapes)},
    "prophet": {"mape": sum(prophet_mapes) / len(prophet_mapes)},
}
print_leaderboard(results, "mape", lower_is_better=True)
print()

sig_result = paired_significance_test(naive_mapes, prophet_mapes)
print(sig_result["interpretation"])