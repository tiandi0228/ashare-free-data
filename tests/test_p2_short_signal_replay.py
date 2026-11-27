import unittest
from collector.p2_short_signal_replay import signals
from collector.p4_curated_session_exit import sessions_between
class SignalTests(unittest.TestCase):
    def rows(self):
        return [dict(date=d,close="10",tradestatus="1") for d in sessions_between("2026-10-21","2026-11-25")][:21]
    def test_cross_and_no_future_dependency(self):
        r=self.rows();r[-1]["close"]="11"
        self.assertEqual(len(signals(r,"sh.600150")),1)
        self.assertEqual(signals(r[:-1],"sh.600150"),[])
    def test_suspension_blocks(self):
        r=self.rows();r[-1]["close"]="11";r[5]["tradestatus"]="0"
        self.assertEqual(signals(r,"sh.600150"),[])
    def test_missing_session_blocks(self):
        r=self.rows();r[-1]["close"]="11";r.pop(5)
        self.assertEqual(signals(r,"sh.600150"),[])
