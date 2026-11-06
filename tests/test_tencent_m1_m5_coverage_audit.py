import unittest
from collector.tencent_m1_m5_coverage_audit import labels,summarize

class TestExactCoverage(unittest.TestCase):
    def test_exact_m1_and_m5_counts(self):
        self.assertEqual(len(labels("2026-11-05","m1")),240)
        self.assertEqual(len(labels("2026-11-05","m5")),48)

    def test_240_m1_records_spanning_two_days_are_not_full_day(self):
        day="20261105"
        stamps=sorted(labels("2026-11-05","m1"))[:100]
        rows=[{"timestamp_cn":t,"high":11,"low":9} for t in stamps]
        res=summarize(rows,day,"m1")
        self.assertFalse(res["full_canonical_label_coverage"])
        self.assertEqual(res["missing_count"],140)

    def test_complete_and_offbyone_rejected(self):
        day="20261105"
        rows=[{"timestamp_cn":t,"high":11,"low":9} for t in sorted(labels("2026-11-05","m5"))]
        self.assertTrue(summarize(rows,day,"m5")["full_canonical_label_coverage"])
        rows[0]["timestamp_cn"]="202611050934"
        self.assertFalse(summarize(rows,day,"m5")["full_canonical_label_coverage"])

    def test_wrong_period_rejected(self):
        with self.assertRaises(ValueError):
            labels("2026-11-05","m15")

if __name__=="__main__":unittest.main()
