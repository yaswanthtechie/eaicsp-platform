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


if __name__ == "__main__":
    unittest.main()