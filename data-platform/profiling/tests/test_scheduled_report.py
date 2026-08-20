import unittest

from src.scheduled_report import check_quality_threshold


class TestScheduledReport(unittest.TestCase):

    def test_alert_when_score_below_threshold(self):
        report = {
            "quality_score": {
                "score": 70
            }
        }

        result = check_quality_threshold(
            report,
            threshold=80
        )

        self.assertEqual(result["status"], "ALERT")
        self.assertEqual(result["score"], 70)

    def test_ok_when_score_meets_threshold(self):
        report = {
            "quality_score": {
                "score": 90
            }
        }

        result = check_quality_threshold(
            report,
            threshold=80
        )

        self.assertEqual(result["status"], "OK")


if __name__ == "__main__":
    unittest.main()