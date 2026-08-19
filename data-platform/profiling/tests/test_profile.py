import unittest
import pandas as pd

from src.profile import profile, detect_pii


class TestProfile(unittest.TestCase):

    def test_null_count(self):
        df = pd.DataFrame({
            "quantity_sold": [10, None, 20, 30]
        })

        report = profile(df)

        self.assertEqual(
            report["column_summary"][0]["null_count"],
            1
        )

    def test_pii_email_is_high(self):
        df = pd.DataFrame({
            "email": ["user@example.com"]
        })

        pii_report = detect_pii(df)

        self.assertEqual(
            pii_report[0]["severity"],
            "HIGH"
        )

    def test_pii_numeric_is_low(self):
        df = pd.DataFrame({
            "quantity_sold": [10, 20, 30]
        })

        pii_report = detect_pii(df)

        self.assertEqual(
            pii_report[0]["severity"],
            "LOW"
        )


if __name__ == "__main__":
    unittest.main()
