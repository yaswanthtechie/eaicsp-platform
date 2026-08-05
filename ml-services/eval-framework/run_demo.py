import pandas as pd
from src.metrics import mape, rmse
from src.baseline import naive_forecast
from src.splits import time_based_split
from src.report import compare_models

df = pd.read_csv("data/example_retail_sales.csv")
df.columns = ["date", "y"]
df["date"] = pd.to_datetime(df["date"])

train, test = time_based_split(df, "date", test_size=0.2)
actual = test["y"].tolist()
naive_preds = naive_forecast(actual)

results = {
    "naive": {
        "mape": mape(actual, naive_preds),
        "rmse": rmse(actual, naive_preds),
    }
}

print(f"Train size: {len(train)}, Test size: {len(test)}")
compare_models(results)