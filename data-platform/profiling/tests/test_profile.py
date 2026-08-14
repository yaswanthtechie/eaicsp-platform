import unittest
import pandas as pd

from src.profile import profile


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


if __name__ == "__main__":
    unittest.main()