import unittest
import pandas as pd

from src.outliers import find_outliers


class TestOutliers(unittest.TestCase):

    def test_find_outliers(self):
        # Sample data with one obvious outlier
        series = pd.Series([10, 20, 30, 40, 99999])

        result = find_outliers(series)

        self.assertEqual(result["outlier_count"], 1)


if __name__ == "__main__":
    unittest.main()