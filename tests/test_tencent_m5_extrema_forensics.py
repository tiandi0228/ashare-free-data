import unittest
from collector.tencent_m5_extrema_forensics import attribute

class TestAttribution(unittest.TestCase):
    def test_low_discrepancy_carries_exact_minute_provenance(self):
        bars=[
            {"timestamp_cn":"202611050935","open":10.0,"high":10.2,"low":9.9,"close":10.1},
            {"timestamp_cn":"202611050940","open":10.1,"high":10.4,"low":10.0,"close":10.2},
        ]
        row={"tradestatus":"1","open":"10.0","high":"10.4","low":"9.5","close":"10.2"}
        obs=attribute(bars,{"2026-11-05":row},"sz002249")[0]
        self.assertEqual(obs["low_difference_cn_yuan"],"0.4")
        self.assertEqual(obs["low_observed_at_cn"],["202611050935"])
        self.assertTrue(obs["high_match"])
        self.assertFalse(obs["low_match"])
        self.assertFalse(obs["same_day_ohlc_agrees_within_1_tick"])
        self.assertTrue(obs["extreme_mismatch_hypotheses"])

    def test_exact_prices_do_not_invent_mismatch(self):
        bars=[{"timestamp_cn":"202611050935","open":10,"high":10.4,"low":9.5,"close":10.2}]
        row={"tradestatus":"1","open":"10","high":"10.4","low":"9.5","close":"10.2"}
        obs=attribute(bars,{"2026-11-05":row},"sh600519")[0]
        self.assertTrue(obs["same_day_ohlc_agrees_within_1_tick"])
        self.assertEqual(obs["extreme_mismatch_hypotheses"],[])

    def test_nontrading_day_never_compared(self):
        bars=[{"timestamp_cn":"202611050935","open":10,"high":10.4,"low":9.5,"close":10.2}]
        row={"tradestatus":"0","open":"","high":"","low":"","close":""}
        self.assertEqual(attribute(bars,{"2026-11-05":row},"sh600519"),[])

if __name__=="__main__":unittest.main()
