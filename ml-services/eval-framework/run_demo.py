import pandas as pd
from eval_framework.metrics import mape, rmse
from eval_framework.baseline import naive_forecast
from eval_framework.splits import time_based_split
from eval_framework.report import compare_models

URL = "https://raw.githubusercontent.com/facebook/prophet/main/examples/example_retail_sales.csv"
df = pd.read_csv(URL)
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