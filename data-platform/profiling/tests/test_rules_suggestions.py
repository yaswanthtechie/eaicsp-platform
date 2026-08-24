import unittest

from src.rules_suggestions import suggest_rules, write_rules_yaml


class TestRulesSuggestions(unittest.TestCase):

    def test_suggest_not_null_rule(self):
        report = {
            "column_summary": [
                {
                    "column": "sku_id",
                    "null_percent": 0.0,
                    "dtype": "object"
                }
            ]
        }

        result = suggest_rules(report)

        self.assertEqual(
            result["rules"],
            [
                {
                    "column": "sku_id",
                    "rule": "not_null"
                }
            ]
        )

    def test_suggest_range_rule(self):
        report = {
            "column_summary": [
                {
                    "column": "quantity_sold",
                    "null_percent": 0.0,
                    "dtype": "int64"
                }
            ],
            "statistics": {
                "quantity_sold": {
                    "min": 1,
                    "max": 500
                }
            }
        }

        result = suggest_rules(report)

        self.assertIn(
            {
                "column": "quantity_sold",
                "rule": "not_null"
            },
            result["rules"]
        )

        self.assertIn(
            {
                "column": "quantity_sold",
                "rule": "range",
                "min": 1.0,
                "max": 500.0
            },
            result["rules"]
        )

    def test_write_rules_yaml(self):
        report = {
            "column_summary": [
                {
                    "column": "sku_id",
                    "null_percent": 0.0,
                    "dtype": "object"
                },
                {
                    "column": "quantity_sold",
                    "null_percent": 0.0,
                    "dtype": "float64"
                }
            ],
            "statistics": {
                "quantity_sold": {
                    "min": 1.0,
                    "max": 500.0
                }
            }
        }

        import tempfile
        from pathlib import Path
        import yaml

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "suggested_rules.yaml"

            write_rules_yaml(
                report,
                output_path=output_path
            )

            self.assertTrue(output_path.exists())

            with open(output_path, "r", encoding="utf-8") as file:
                result = yaml.safe_load(file)

            self.assertIn("rules", result)
            self.assertEqual(len(result["rules"]), 3)


if __name__ == "__main__":
    unittest.main()