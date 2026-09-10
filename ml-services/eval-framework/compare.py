import argparse
import json
import sys
from src.report import compare_models


def load_results(path: str) -> dict:
    """Loads a JSON file shaped like {model_name: {metric: value}}."""
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict) or len(data) == 0:
        raise ValueError("results JSON must be a non-empty object of {model_name: {metric: value}}")
    return data


def main():
    parser = argparse.ArgumentParser(description="Standalone model comparison CLI")
    parser.add_argument("--results", required=True, help="Path to a results JSON file")
    args = parser.parse_args()

    try:
        results = load_results(args.results)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"Error loading {args.results}: {e}")
        sys.exit(1)

    compare_models(results)


if __name__ == "__main__":
    main()