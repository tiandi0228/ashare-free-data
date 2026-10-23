import unittest
from datetime import date
from collector.p4_sse_holiday_crosscheck import check_dates
class NoticeTests(unittest.TestCase):
    def test_weekend_and_official_holiday_rejected(self):
        r=check_dates([date(2026,1,1),date(2026,1,3),date(2026,1,5)])
        self.assertEqual(r["unexpected_holiday_dates"],["2026-01-01","2026-01-03"])
        self.assertEqual(r["unexpected_weekend_dates"],["2026-01-03"])
    def test_unsupported_year_fails_closed(self):
        with self.assertRaises(ValueError):check_dates([date(2024,12,31)])
    def test_reopening_date(self):
        r=check_dates([date(2026,2,24),date(2026,2,25)])
        self.assertFalse(r["unexpected_holiday_dates"])
        self.assertFalse(r["missing_expected_weekdays"])
if __name__=="__main__":unittest.main()
