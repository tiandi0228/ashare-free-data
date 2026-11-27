import unittest
from collector.p2_short_trend_strata import classify
from collector.p4_curated_session_exit import sessions_between
class StrataTests(unittest.TestCase):
    def rows(self):
        days=sessions_between("2026-07-01","2026-11-25")[-61:]
        return [dict(date=d,close=str(i+10),volume="100",tradestatus="1") for i,d in enumerate(days)]
    def test_prefix_and_volume(self):
        r=self.rows();day=r[-2]["date"];r[-2]["volume"]="150"
        self.assertEqual(classify(r,day),"TREND_VOLUME")
        r[-1].update(close="1",volume="999999",tradestatus="0")
        self.assertEqual(classify(r,day),"TREND_VOLUME")
    def test_missing_and_halt(self):
        r=self.rows();day=r[-1]["date"];r[-5]["tradestatus"]="0"
        self.assertEqual(classify(r,day),"WINDOW_UNAVAILABLE")
        r=self.rows();r.pop(-5)
        self.assertEqual(classify(r,day),"WINDOW_UNAVAILABLE")
    def test_volume_excludes_current(self):
        r=self.rows();r[-1]["volume"]="149"
        self.assertEqual(classify(r,r[-1]["date"]),"TREND_NO_VOLUME")
