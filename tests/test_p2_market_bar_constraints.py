"""Offline bar plausibility does not prove price fills or trading eligibility."""
import unittest
from collector.p2_market_bar_constraints import check

def fixture():
    return {"code":"002249","is_st":False,"halted":False,"bars":[{
        "time":"2026-11-03T10:30:00+08:00",
        "open":"10.00","high":"10.15","low":"9.95","close":"10.10",
        "daily_lower_limit":"9.00","daily_upper_limit":"11.00",
        "volume_shares":10000,"is_final":True}]}

class MarketBarConstraintTests(unittest.TestCase):
    def test_plausible_bar_never_authorizes_trades(self):
        r=check(fixture())
        self.assertEqual(r["state"],"STRUCTURAL_PLAUSIBILITY_ONLY_NOT_EXECUTABLE")
        self.assertFalse(r["simulated_fill_verified"])
        self.assertFalse(r["trade_calendar_certified"])
        self.assertFalse(r["limit_prices_certified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
    def test_outside_exchange_limit_is_rejected(self):
        x=fixture();x["bars"][0]["high"]="11.05"
        self.assertIn("BAR_0_OHLC_OR_DAILY_LIMIT_CONFLICT",check(x)["reasons"])
    def test_invalid_ohlc_rejected(self):
        x=fixture();x["bars"][0]["low"]="10.12"
        self.assertIn("BAR_0_OHLC_OR_DAILY_LIMIT_CONFLICT",check(x)["reasons"])
    def test_no_future_unfinalized_bars(self):
        x=fixture();x["bars"][0]["is_final"]=False
        self.assertEqual(check(x)["state"],"REJECTED")
    def test_session_and_weekend_rejected(self):
        for stamp in ("2026-11-03T12:10:00+08:00",
                      "2026-11-07T10:30:00+08:00"):
            with self.subTest(stamp=stamp):
                x=fixture();x["bars"][0]["time"]=stamp
                self.assertIn("BAR_0_OUTSIDE_CONTINUOUS_SESSION",check(x)["reasons"])
    def test_volume_and_st_rejected(self):
        for v in (-1,1.2,True):
            with self.subTest(volume=v):
                x=fixture();x["bars"][0]["volume_shares"]=v
                self.assertIn("BAR_0_INVALID_VOLUME",check(x)["reasons"])
        x=fixture();x["is_st"]=None
        self.assertEqual(check(x)["reasons"],["SECURITY_STATUS_UNVERIFIED"])
    def test_duplicates_and_order_rejected(self):
        x=fixture();x["bars"].append(dict(x["bars"][0]))
        self.assertIn("BAR_1_UNORDERED_OR_DUPLICATE",check(x)["reasons"])
    def test_naive_timestamp_and_incorrect_precision_rejected(self):
        x=fixture();x["bars"][0]["time"]="2026-11-03T10:30:00"
        self.assertIn("BAR_0_MALFORMED",check(x)["reasons"])
        x=fixture();x["bars"][0]["close"]="10.105"
        self.assertIn("BAR_0_MALFORMED",check(x)["reasons"])
    def test_missing_evidence_and_non_mainboard_rejected(self):
        for change in ({"code":"300015"},{"code":"688001"},{"bars":[]},
                       {"bars":[{"time":"2026-11-03T10:30:00+08:00"}]}):
            with self.subTest(change=change):
                x=fixture();x.update(change)
                self.assertEqual(check(x)["state"],"REJECTED")
                self.assertEqual(check(x)["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
