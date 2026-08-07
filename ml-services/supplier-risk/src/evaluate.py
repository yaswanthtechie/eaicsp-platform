"""
Evaluation script for the Supplier Risk NLP pipeline.
"""

from collections import defaultdict
from pathlib import Path
import json
from typing import Any, Dict, List
from src.predict import predict
from src.sentiment import init_model


def load_dataset(filepath: str) -> List[Dict[str, Any]]:
    """
    Load the evaluation dataset from a JSON file.
    """
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def run_evaluation() -> None:
    """
    Run the evaluation pipeline and print the
    risk summary for each supplier.
    """
    print("Initializing FinBERT model...")
    init_model()

    dataset_path = Path(__file__).parent / "supplier_headlines.json"
    dataset = load_dataset(str(dataset_path))

    grouped_headlines = defaultdict(list)

    for item in dataset:
        grouped_headlines[item["supplier"]].append(
            item["headline"]
        )

    print("\n========== Evaluation Results ==========\n")

    for supplier, headlines in grouped_headlines.items():

        summary = predict(
            supplier_name=supplier,
            headlines=headlines,
        )

        print(f"Supplier : {summary['supplier']}")
        print(f"Risk Score : {summary['risk_score']}")

        print("\nSignals:")

        if not summary["signals"]:
            print("- None")
        else:
            for signal in summary["signals"]:
                print(
                    f"- {signal['keyword']} "
                    f"(weight={signal['weight']})"
                )

        print("\nSentiment Breakdown")
        print(
            f"Positive : "
            f"{summary['sentiment_breakdown']['positive']}"
        )
        print(
            f"Neutral  : "
            f"{summary['sentiment_breakdown']['neutral']}"
        )
        print(
            f"Negative : "
            f"{summary['sentiment_breakdown']['negative']}"
        )

        print("\nTop 3 Highest Risk Headlines")

        if not summary["top_worst_3"]:
            print("- None")
        else:
            for index, headline in enumerate(
                summary["top_worst_3"],
                start=1,
            ):
                print(
                    f"{index}. "
                    f"{headline['headline']}"
                )

        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    run_evaluation()