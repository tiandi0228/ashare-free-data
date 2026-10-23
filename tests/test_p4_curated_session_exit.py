import unittest
from collector.p4_curated_session_exit import sessions_between,research_exit
class Tests(unittest.TestCase):
    def test_spring_festival_not_calendar_days(self):
        self.assertEqual(sessions_between("2026-02-13","2026-02-25"),
                         ["2026-02-13","2026-02-24","2026-02-25"])
    def test_friday_before_d3(self):
        x=research_exit("2026-02-26")
        self.assertEqual(x["candidate_friday_exit"],"2026-02-27")
        self.assertEqual(x["candidate_earlier_exit"],"2026-02-27")
        self.assertEqual(x["trade_gate"],"BLOCKED")
    def test_unsupported_fails(self):
        with self.assertRaises(ValueError):sessions_between("2026-12-20","2027-01-10")
    def test_holiday_entry_rejected(self):
        with self.assertRaises(ValueError):research_exit("2026-02-16")
if __name__=="__main__":unittest.main()
