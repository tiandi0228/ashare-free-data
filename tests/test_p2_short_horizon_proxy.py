import unittest
from collector.p2_short_horizon_proxy import observe
class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.days=["2026-11-16","2026-11-17","2026-11-18","2026-11-19","2026-11-20","2026-11-23"]
        self.bars={d:dict(open="10",close="10",volume="100",tradestatus="1") for d in self.days}
    def test_next_open_and_t1(self):
        r=observe(self.days[0],self.bars,self.days,3)
        self.assertEqual((r["entry_day"],r["exit_day"],r["shares"]),("2026-11-17","2026-11-19",700))
        self.assertLess(float(r["net_deployed_return_pct"]),0)
        self.assertFalse(r["execution_verified"])
    def test_censored(self):
        self.assertEqual(observe(self.days[-2],self.bars,self.days,3)["status"],"RIGHT_CENSORED")
    def test_missing(self):
        del self.bars[self.days[2]]
        self.assertEqual(observe(self.days[0],self.bars,self.days,3)["status"],"MISSING_VENDOR_SESSION")
    def test_halt(self):
        self.bars[self.days[2]]["tradestatus"]="0"
        self.assertEqual(observe(self.days[0],self.bars,self.days,3)["status"],"VENDOR_NONTRADABLE_WINDOW")
    def test_unaffordable(self):
        self.bars[self.days[1]]["open"]="80"
        self.assertEqual(observe(self.days[0],self.bars,self.days,3)["status"],"UNAFFORDABLE_BOARD_LOT")
    def test_zero_volume(self):
        self.bars[self.days[1]]["volume"]="0"
        self.assertEqual(observe(self.days[0],self.bars,self.days,3)["status"],"ZERO_VOLUME_WINDOW")
