"""Fail-closed contract tests: fee scenarios are never broker fills."""
import copy
import unittest
from decimal import Decimal

from collector.p4_observed_fee_friction import audit, exposure


def sample():
    price={
        "issuer":"sh.600000",
        "original_csv_sha256":"b"*64,
        "signal_known_after_close_date":"2026-01-05",
        "next_vendor_date":"2026-01-06",
        "third_vendor_date":"2026-01-08",
        "signal_close":"10",
        "next_vendor_open":"11",
        "third_vendor_close":"12",
        "overnight_open_gap_pct":"10.0000",
        "next_open_to_third_close_change_pct":"9.0909",
        "next_open_fill_assumed":False,
        "exit_close_fill_assumed":False,
        "trade_return":None,
        "T_plus_1_execution_verified":False,
    }
    return {
        "phase":"P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES",
        "status":"OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST",
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
        "fills_assumed":0,"trades_assumed":0,
        "portfolio_pnl_computed":False,
        "strategy_backtest_certified":False,
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "archive_commit_sha":"a"*40,
        "holdout_cutoff_inclusive":"2025-12-31",
        "verified_nonoverlap_events":1,
        "observed_next_open_to_third_close":1,
        "censored_events":0,
        "future_vendor_status_blocked":0,
        "positive_price_changes":1,
        "negative_price_changes":0,
        "flat_price_changes":0,
        "observed_price_pairs":[price],
    }


class FeeFrictionTests(unittest.TestCase):
    def test_100_share_commission_floor_transfer_and_stamp(self):
        sh=exposure(Decimal("11"),Decimal("12"),"sh.600000",0)
        sz=exposure(Decimal("11"),Decimal("12"),"sz.002249",0)
        self.assertEqual(sh["entry_commission_cny"],Decimal("5.00"))
        self.assertEqual(sh["exit_commission_cny"],Decimal("5.00"))
        self.assertEqual(sh["exit_stamp_cny"],Decimal("0.60"))
        self.assertEqual(sh["entry_transfer_cny"],Decimal("0.01"))
        self.assertEqual(sh["exit_transfer_cny"],Decimal("0.01"))
        self.assertEqual(sh["modelled_total_friction_cny"],Decimal("10.62"))
        self.assertEqual(sh["modelled_margin_after_friction_cny"],Decimal("89.38"))
        self.assertEqual(sz["entry_transfer_cny"],Decimal("0.00"))
        self.assertEqual(sz["modelled_total_friction_cny"],Decimal("10.60"))
        self.assertTrue(sh["affordable_one_lot_proxy"])

    def test_two_scenarios_never_certify_a_trade(self):
        r=audit(sample())
        self.assertEqual(r["status"],
                         "OBSERVED_VENDOR_PRICE_FRICTION_SCENARIOS_NOT_BACKTEST")
        self.assertEqual([x["assumed_slippage_bps_each_side"]
                          for x in r["scenarios"]],[0,10])
        self.assertEqual(r["scenarios"][0]["one_lot_proxy_within_cash_cap"],1)
        self.assertEqual(r["scenarios"][0]["modelled_positive_margin_pairs"],1)
        self.assertEqual(r["scenarios"][1]["modelled_positive_margin_pairs"],1)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["actionable_buy_signals"],[])
        self.assertFalse(r["risk_gate_verified"])
        self.assertFalse(r["strategy_backtest_certified"])
        self.assertFalse(r["trade_authorized"])
        self.assertFalse(r["trade_returns_computed"])
        self.assertIsNone(r["scenarios"][0]["win_rate"])
        self.assertEqual(r["scenarios"][0]["broker_trade_count"],0)

    def test_cash_cap_cannot_be_fudged_from_positive_prices(self):
        p=sample()
        row=p["observed_price_pairs"][0]
        row["signal_close"]="90"
        row["next_vendor_open"]="90"
        row["third_vendor_close"]="100"
        row["overnight_open_gap_pct"]="0.0000"
        row["next_open_to_third_close_change_pct"]="11.1111"
        r=audit(p)
        self.assertEqual(r["observed_price_pairs"],1)
        for x in r["scenarios"]:
            self.assertEqual(x["one_lot_proxy_within_cash_cap"],0)
            self.assertEqual(x["one_lot_proxy_exceeds_cash_cap"],1)
            self.assertEqual(x["modelled_positive_margin_pairs"],0)
        self.assertFalse(r["trade_authorized"])

    def test_censoring_is_never_counted_as_zero_outcome(self):
        p=sample()
        p["verified_nonoverlap_events"]=2
        p["censored_events"]=1
        r=audit(p)
        self.assertEqual(r["observed_price_pairs"],1)
        self.assertEqual(r["censored_events"],1)
        self.assertEqual(r["observed_positive_price_changes"],1)

    def test_unsafe_proxy_forged_execution_or_tampered_delta_rejected(self):
        for action in (
            lambda p: p.update(trade_gate="OPEN"),
            lambda p: p["orders"].append({"side":"BUY"}),
            lambda p: p["observed_price_pairs"][0].update(next_open_fill_assumed=True),
            lambda p: p["observed_price_pairs"][0].update(trade_return="10"),
            lambda p: p["observed_price_pairs"][0].update(next_open_to_third_close_change_pct="20.0000"),
            lambda p: p["observed_price_pairs"][0].update(overnight_open_gap_pct="0.0000"),
            lambda p: p["observed_price_pairs"][0].update(issuer="sz.300015"),
            lambda p: p["observed_price_pairs"][0].update(original_csv_sha256="x"*64),
            lambda p: p["observed_price_pairs"][0].update(third_vendor_date="2026-01-06"),
        ):
            with self.subTest(action=action):
                p=sample()
                action(p)
                self.assertEqual(audit(p)["status"],"REJECTED")

    def test_duplicate_event_and_invalid_counter_rejected(self):
        p=sample()
        p["verified_nonoverlap_events"]=2
        p["observed_next_open_to_third_close"]=2
        p["positive_price_changes"]=2
        p["observed_price_pairs"].append(copy.deepcopy(p["observed_price_pairs"][0]))
        self.assertEqual(audit(p)["reason"],"DUPLICATE_ISSUER_EVENT")
        p=sample()
        p["observed_next_open_to_third_close"]=True
        self.assertEqual(audit(p)["reason"],"UNRECONCILED_EVENT_COUNTERS")

    def test_fee_floor_can_erase_small_positive_observed_change(self):
        p=sample()
        row=p["observed_price_pairs"][0]
        row["signal_close"]="10"
        row["next_vendor_open"]="10"
        row["third_vendor_close"]="10.01"
        row["overnight_open_gap_pct"]="0.0000"
        row["next_open_to_third_close_change_pct"]="0.1000"
        result=audit(p)
        self.assertEqual(result["scenarios"][0]["price_up_pairs_within_cash_cap"],1)
        self.assertEqual(result["scenarios"][0]["price_up_but_friction_erases_margin"],1)
        self.assertEqual(result["scenarios"][0]["modelled_negative_margin_pairs"],1)
        self.assertFalse(result["strategy_backtest_certified"])


if __name__=="__main__":
    unittest.main()
