import unittest
import tempfile
from pathlib import Path

import yaml

from src.rules_suggestions import (
    suggest_rules,
    write_rules_yaml,
    validate_rules_config,
)


class TestRulesSuggestions(unittest.TestCase):

    # ---------------------------------
    # Test 1 - not_null rule
    # ---------------------------------
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
            result["version"],
            "1.0.0"
        )

        self.assertEqual(
            result["rules"],
            [
                {
                    "name": "sku_id_not_null",
                    "field": "sku_id",
                    "type": "not_null",
                    "severity": "ERROR",
                }
            ]
        )

    # ---------------------------------
    # Test 2 - range rule
    # ---------------------------------
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
                "name": "quantity_sold_not_null",
                "field": "quantity_sold",
                "type": "not_null",
                "severity": "ERROR",
            },
            result["rules"]
        )

        self.assertIn(
            {
                "name": "quantity_sold_range",
                "field": "quantity_sold",
                "type": "range",
                "min": 1.0,
                "max": 500.0,
                "severity": "WARNING",
            },
            result["rules"]
        )

    # ---------------------------------
    # Test 3 - YAML generation
    # ---------------------------------
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

        with tempfile.TemporaryDirectory() as temp_dir:

            output_path = (
                Path(temp_dir)
                / "suggested_rules.yaml"
            )

            returned_path = write_rules_yaml(
                report,
                output_path=output_path
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(
                returned_path,
                output_path
            )

            with open(
                output_path,
                "r",
                encoding="utf-8"
            ) as file:

                result = yaml.safe_load(file)

            self.assertEqual(
                result["version"],
                "1.0.0"
            )

            self.assertIn(
                "rules",
                result
            )

            self.assertEqual(
                len(result["rules"]),
                3
            )

            # Verify generated YAML follows
            # Tharun's documented structure.
            for rule in result["rules"]:
                self.assertIn("name", rule)
                self.assertIn("type", rule)
                self.assertIn("severity", rule)

    # ---------------------------------
    # Test 4 - Valid configuration
    # ---------------------------------
    def test_validate_valid_rules_config(self):

        config = {
            "version": "1.0.0",
            "rules": [
                {
                    "name": "sku_id_not_null",
                    "field": "sku_id",
                    "type": "not_null",
                    "severity": "ERROR",
                },
                {
                    "name": "quantity_sold_range",
                    "field": "quantity_sold",
                    "type": "range",
                    "min": 0,
                    "max": 100000,
                    "severity": "WARNING",
                },
            ]
        }

        self.assertTrue(
            validate_rules_config(config)
        )

    # ---------------------------------
    # Test 5 - Invalid version
    # ---------------------------------
    def test_validate_invalid_version(self):

        config = {
            "version": "2.0.0",
            "rules": []
        }

        with self.assertRaises(ValueError):
            validate_rules_config(config)

    # ---------------------------------
    # Test 6 - Invalid rule type
    # ---------------------------------
    def test_validate_invalid_rule_type(self):

        config = {
            "version": "1.0.0",
            "rules": [
                {
                    "name": "bad_rule",
                    "field": "sku_id",
                    "type": "execute_code",
                    "severity": "ERROR",
                }
            ]
        }

        with self.assertRaises(ValueError):
            validate_rules_config(config)

    # ---------------------------------
    # Test 7 - Missing field
    # ---------------------------------
    def test_validate_missing_field(self):

        config = {
            "version": "1.0.0",
            "rules": [
                {
                    "name": "sku_id_not_null",
                    "type": "not_null",
                    "severity": "ERROR",
                }
            ]
        }

        with self.assertRaises(ValueError):
            validate_rules_config(config)

    # ---------------------------------
    # Test 8 - Invalid severity
    # ---------------------------------
    def test_validate_invalid_severity(self):

        config = {
            "version": "1.0.0",
            "rules": [
                {
                    "name": "sku_id_not_null",
                    "field": "sku_id",
                    "type": "not_null",
                    "severity": "CRITICAL",
                }
            ]
        }

        with self.assertRaises(ValueError):
            validate_rules_config(config)

    # ---------------------------------
    # Test 9 - Invalid range
    # ---------------------------------
    def test_validate_invalid_range(self):

        config = {
            "version": "1.0.0",
            "rules": [
                {
                    "name": "quantity_range",
                    "field": "quantity_sold",
                    "type": "range",
                    "min": 100,
                    "max": 10,
                    "severity": "WARNING",
                }
            ]
        }

        with self.assertRaises(ValueError):
            validate_rules_config(config)

    # ---------------------------------
    # Test 10 - Malicious / unsupported
    # rule type is rejected
    # ---------------------------------
    def test_validate_malicious_rule_type(self):

        config = {
            "version": "1.0.0",
            "rules": [
                {
                    "name": "malicious_rule",
                    "field": "sku_id",
                    "type": "__import__('os').system('whoami')",
                    "severity": "ERROR",
                }
            ]
        }

        with self.assertRaises(ValueError):
            validate_rules_config(config)


if __name__ == "__main__":
    unittest.main()