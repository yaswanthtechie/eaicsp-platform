import pandas as pd
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
# "toy model" = naive shifted by 2 instead of 1, standing in for a second real model
# for demonstration purposes, since no second model is wired into eval-framework yet
toy_model_mapes = []

for train, test in folds:
    actual = test["y"].tolist()
    naive_preds = naive_forecast(actual)
    naive_mapes.append(mape(actual, naive_preds))

    shifted = [actual[0], actual[0]] + actual[:-2]
    toy_model_mapes.append(mape(actual, shifted))

print("Naive MAPE per fold:", [round(x, 2) for x in naive_mapes])
print("Toy model MAPE per fold:", [round(x, 2) for x in toy_model_mapes])
print()

results = {
    "naive": {"mape": sum(naive_mapes) / len(naive_mapes)},
    "toy_model": {"mape": sum(toy_model_mapes) / len(toy_model_mapes)},
}
print_leaderboard(results, "mape", lower_is_better=True)
print()

sig_result = paired_significance_test(naive_mapes, toy_model_mapes)
print(sig_result["interpretation"])