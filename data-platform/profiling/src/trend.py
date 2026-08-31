import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from pathlib import Path

from src.monitoring import MonitoringHistory


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = BASE_DIR / "reports" / "quantity_sold_null_trend.png"


def generate_null_rate_trend(
    column_name="quantity_sold",
    output_path=DEFAULT_OUTPUT_PATH
):
    monitoring = MonitoringHistory()

    trend = monitoring.get_column_trend(column_name)

    values = trend["values"]

    if len(values) < 1:
        print(f"No historical data available for {column_name}")
        return None

    run_numbers = list(range(1, len(values) + 1))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 5))

    plt.plot(run_numbers, values, marker="o")

    plt.title(f"{column_name} Null Rate Trend")
    plt.xlabel("Profiling Run")
    plt.ylabel("Null Rate (%)")

    plt.xticks(run_numbers)

    plt.tight_layout()

    plt.savefig(output_path)
    plt.close()

    print(f"Trend chart saved to: {output_path}")

    return output_path