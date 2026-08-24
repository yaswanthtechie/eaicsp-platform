import unittest

import pandas as pd

from src.anomaly import analyze_anomaly_correlation


class TestAnomalyCorrelation(unittest.TestCase):

    def test_anomaly_correlation(self):
        df = pd.DataFrame({
            "quantity_sold": [10, 20, 30, 40, 99999],
            "unit_price": [100, 200, 300, 400, None]
        })

        result = analyze_anomaly_correlation(df)

        self.assertEqual(result["outlier_rows"], 1)
        self.assertEqual(len(result["findings"]), 1)

        finding = result["findings"][0]

        self.assertEqual(finding["column"], "unit_price")
        self.assertEqual(finding["issue"], "Missing values")

    def test_empty_dataframe(self):
        df = pd.DataFrame({
            "quantity_sold": pd.Series(dtype=float),
            "unit_price": pd.Series(dtype=float)
        })

        result = analyze_anomaly_correlation(df)

        self.assertEqual(result["outlier_rows"], 0)
        self.assertEqual(result["findings"], [])

    def test_no_outliers(self):
        df = pd.DataFrame({
            "quantity_sold": [10, 20, 30, 40, 50],
            "unit_price": [100, 200, 300, 400, 500]
        })

        result = analyze_anomaly_correlation(df)

        self.assertEqual(result["outlier_rows"], 0)
        self.assertEqual(result["findings"], [])

    def test_single_row(self):
        df = pd.DataFrame({
            "quantity_sold": [10],
            "unit_price": [100]
        })

        result = analyze_anomaly_correlation(df)

        self.assertEqual(result["outlier_rows"], 0)
        self.assertEqual(result["findings"], [])

    def test_all_null_target_column(self):
        df = pd.DataFrame({
            "quantity_sold": [None, None, None],
            "unit_price": [100, 200, 300]
        })

        result = analyze_anomaly_correlation(df)

        self.assertEqual(result["outlier_rows"], 0)
        self.assertEqual(result["findings"], [])

    def test_non_numeric_target_column(self):
        df = pd.DataFrame({
            "quantity_sold": ["10", "20", "30", "99999"],
            "unit_price": [100, 200, 300, 400]
        })

        result = analyze_anomaly_correlation(df)

        self.assertEqual(result["outlier_rows"], 0)
        self.assertEqual(result["findings"], [])

    def test_cross_column_outlier_correlation(self):
        df = pd.DataFrame({
            "quantity_sold": [
                10, 11, 12, 13, 14,
                15, 16, 17, 18, 99999
            ],
            "unit_price": [
                100, 101, 102, 103, 104,
                105, 106, 107, 108, 99999
            ]
        })

        result = analyze_anomaly_correlation(df)

        self.assertEqual(result["outlier_rows"], 1)

        finding = next(
            finding
            for finding in result["findings"]
            if finding["issue"] == "Other outliers"
        )

        self.assertEqual(finding["column"], "unit_price")
        self.assertEqual(finding["outlier_row_count"], 1)
        self.assertEqual(finding["outlier_row_rate"], 100.0)


if __name__ == "__main__":
    unittest.main()