"""Offline direction audit rejects fabricated outcomes and censored win rates."""
import copy,unittest
from collector.p4_holdout_direction_bias_audit import audit

def fixture():
    observations=[
      {"issuer":"sh.600000","signal_close_day":"2026-01-05",
       "observed_third_later_vendor_day":"2026-01-08",
       "source_csv_sha256":"a"*64,
       "signal_known_after_close_only":True,
       "execution_at_signal_close_assumed":False,"entry_filled":False,
       "trade_return":None,"observed_signal_close":"10",
       "observed_third_later_close":"11",
       "close_to_third_later_close_change_pct":"10.0000"},
      {"issuer":"sz.002249","signal_close_day":"2026-01-06",
       "observed_third_later_vendor_day":"2026-01-09",
       "source_csv_sha256":"b"*64,
       "signal_known_after_close_only":True,
       "execution_at_signal_close_assumed":False,"entry_filled":False,
       "trade_return":None,"observed_signal_close":"10",
       "observed_third_later_close":"9",
       "close_to_third_later_close_change_pct":"-10.0000"},
      {"issuer":"sh.600000","signal_close_day":"2026-02-12",
       "observed_third_later_vendor_day":"2026-02-17",
       "source_csv_sha256":"a"*64,
       "signal_known_after_close_only":True,
       "execution_at_signal_close_assumed":False,"entry_filled":False,
       "trade_return":None,"observed_signal_close":"10",
       "observed_third_later_close":"10",
       "close_to_third_later_close_change_pct":"0.0000"}]
    return {"phase":"P4_REAL_HOLDOUT_FORWARD_PRICE_OBSERVATIONS",
            "status":"HOLDOUT_PRICE_OBSERVATIONS_NOT_BACKTEST",
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "actionable_buy_signals":[],"strategy_backtest_certified":False,
            "historical_OOS_validated":False,"historical_PIT_verified":False,
            "returns_computed_as_trades":False,"fills_assumed":0,
            "archive_commit_sha":"c"*40,
            "holdout_cutoff_inclusive":"2025-12-31",
            "verified_ma20_crossing_events":5,
            "observed_with_three_vendor_tradable_rows":3,
            "censored_insufficient_following_rows":1,
            "unscorable_future_vendor_status":1,
            "observed_positive_close_changes":1,
            "observed_negative_close_changes":1,
            "observed_zero_close_changes":1,
            "research_observations":observations}
class DirectionBiasTests(unittest.TestCase):
    def test_audit_explicitly_denies_win_rate(self):
        r=audit(fixture())
        self.assertEqual(r["status"],"DIRECTIONAL_OBSERVATION_BIAS_AUDITED_NOT_STRATEGY")
        self.assertEqual(r["observed_positive_share_pct"],"33.3333")
        self.assertEqual(r["observation_availability_pct"],"60.0000")
        self.assertEqual(r["top_issuer_event_share_pct"],"66.6667")
        self.assertEqual(r["unique_issuers"],2)
        self.assertEqual(len(r["monthly_observation_counts"]),2)
        self.assertFalse(r["win_rate_claimed"])
        self.assertFalse(r["trade_returns_calculated"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
    def test_inconsistent_counts_and_price_change_rejected(self):
        p=fixture();p["observed_positive_close_changes"]=2
        self.assertEqual(audit(p)["reason"],"EVENT_OUTCOME_COUNTERS_INCONSISTENT")
        p=fixture();p["research_observations"][0]["close_to_third_later_close_change_pct"]="11.0000"
        self.assertEqual(audit(p)["reason"],"ROW_0_PRICE_CHANGE_MISMATCH")
    def test_duplicate_signal_and_future_before_signal_rejected(self):
        p=fixture();p["research_observations"][2]["signal_close_day"]="2026-01-05"
        self.assertEqual(audit(p)["reason"],"DUPLICATE_ISSUER_SIGNAL_DAY")
        p=fixture();p["research_observations"][0]["observed_third_later_vendor_day"]="2026-01-04"
        self.assertEqual(audit(p)["reason"],"ROW_0_WRONG_FORWARD_ORDER")
    def test_fake_trade_or_inadequate_provenance_rejected(self):
        for k,v in (("trade_gate","OPEN"),("fills_assumed",1),
                    ("strategy_backtest_certified",True),
                    ("archive_commit_sha","not_sha"),
                    ("orders",[{"side":"BUY"}])):
            p=fixture();p[k]=v
            with self.subTest(k=k):
                self.assertEqual(audit(p)["status"],"REJECTED")
    def test_censored_not_converted_to_observed_losses(self):
        p=fixture();p["verified_ma20_crossing_events"]=6
        self.assertEqual(audit(p)["reason"],"EVENT_OUTCOME_COUNTERS_INCONSISTENT")
        p=fixture();p["research_observations"][0]["trade_return"]="10%"
        self.assertEqual(audit(p)["status"],"REJECTED")
    def test_empty_event_set_is_not_invented(self):
        p=fixture();p["research_observations"]=[]
        for key in ("verified_ma20_crossing_events",
                    "observed_with_three_vendor_tradable_rows",
                    "observed_positive_close_changes","observed_negative_close_changes",
                    "observed_zero_close_changes","censored_insufficient_following_rows",
                    "unscorable_future_vendor_status"):
            p[key]=0
        r=audit(p)
        self.assertEqual(r["status"],"DIRECTIONAL_OBSERVATION_BIAS_AUDITED_NOT_STRATEGY")
        self.assertIsNone(r["observed_positive_share_pct"])
        self.assertEqual(r["unique_issuers"],0)
if __name__=="__main__":unittest.main()
