import unittest
from collector.p2_medium_proxy import medium_signals,observe
from collector.p4_curated_session_exit import sessions_between
class MediumTests(unittest.TestCase):
    def setUp(self):
        self.days=sessions_between("2026-01-01","2026-11-25")
        self.bars={d:dict(date=d,open="10",close="10",volume="100",tradestatus="1") for d in self.days}
    def test_cross_prefix(self):
        i=self.days.index("2026-07-01")
        rows=[dict(self.bars[d]) for d in self.days]
        rows[i]["close"]="11"
        self.assertIn(self.days[i],medium_signals(rows,self.days))
        self.assertEqual(medium_signals(rows[:i+1],self.days),[self.days[i]])
    def test_no_signal_missing_window(self):
        i=self.days.index("2026-07-01")
        rows=[dict(self.bars[d]) for d in self.days[:i+1]]
        rows[-1]["close"]="11";rows.pop(-5)
        self.assertEqual(medium_signals(rows,self.days),[])
    def test_proxy_and_censor(self):
        d=self.days[70]
        r=observe(d,self.bars,self.days,20)
        self.assertEqual(r["entry_day"],self.days[71]);self.assertEqual(r["exit_day"],self.days[90])
        self.assertLess(float(r["net_capital_proxy_pct"]),0)
        self.assertEqual(observe(self.days[-10],self.bars,self.days,60)["status"],"RIGHT_CENSORED")
    def test_nontradable_and_missing(self):
        d=self.days[70];self.bars[self.days[75]]["tradestatus"]="0"
        self.assertEqual(observe(d,self.bars,self.days,20)["status"],"NONTRADABLE_WINDOW")
        del self.bars[self.days[75]]
        self.assertEqual(observe(d,self.bars,self.days,20)["status"],"MISSING_VENDOR_SESSION")
