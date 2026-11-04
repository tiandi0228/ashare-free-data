"""T+1 exit eligibility and same-day two-barrier ambiguity remain research only."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.p4_tplus1_barrier_touch import audit, barrier, touches
from decimal import Decimal


def fixture(folder, mode="both"):
    root=Path(folder)/"archive"
    shard=root/"epoch"/"shard_0000"
    shard.mkdir(parents=True)
    code="sh.600000"
    bars=[
        ("2026-01-05","10","10","10","10"),
        ("2026-01-06","10","10.60","9.70","10"),
        ("2026-01-07","10","10.60","9.70","10"),
        ("2026-01-08","10.80","11","10.50","10.80"),
    ]
    if mode=="gap":
        bars[1]=("2026-01-06","10","10.10","9.90","10")
        bars[2]=("2026-01-07","9.60","9.90","9.55","9.75")
        bars[3]=("2026-01-08","10.70","11","10.50","10.80")
    if mode=="neither":
        bars[1]=("2026-01-06","10","10.10","9.90","10")
        bars[2]=("2026-01-07","10","10.10","9.90","10")
        bars[3]=("2026-01-08","10.05","10.30","9.90","10.20")
    raw=("date,code,open,high,low,close,volume,amount,adjustflag,tradestatus\n" +
         "".join(f"{date},{code},{o},{h},{l},{c},100,1000,3,1\n"
                 for date,o,h,l,c in bars)).encode()
    (shard/"sh_600000.csv").write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest()
    (shard/"quality.json").write_text(json.dumps({"results":[{"code":code,"sha256":sha}]}))
    event={
        "issuer":code,"signal_completed_date":"2026-01-05",
        "source_csv_sha256":sha,
        "three_future_observed_dates":[bar[0] for bar in bars[1:]],
        "three_future_vendor_tradable":True,"fill_assumed":False,
    }
    manifest=Path(folder)/"manifest.json"
    manifest.write_text(json.dumps({
        "cutoff_inclusive":"2025-12-31",
        "archive_commit_sha":"a"*40,
        "nonoverlapping_event_evidence":[event],
    }))
    entry=Decimal(bars[1][1])
    close=Decimal(bars[3][4])
    delta=(close/entry-1)*100
    proxy={"phase":"P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES",
           "status":"OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST",
           "archive_commit_sha":"a"*40,
           "holdout_cutoff_inclusive":"2025-12-31",
           "trade_gate":"BLOCKED","orders":[],
           "executable_candidates":[],"actionable_buy_signals":[],
           "fills_assumed":0,"trades_assumed":0,
           "historical_PIT_verified":False,
           "historical_OOS_validated":False,
           "strategy_backtest_certified":False,
           "verified_nonoverlap_events":1,
           "observed_next_open_to_third_close":1,
           "censored_events":0,"future_vendor_status_blocked":0,
           "observed_price_pairs":[{
               "issuer":code,"original_csv_sha256":sha,
               "signal_known_after_close_date":"2026-01-05",
               "next_vendor_date":"2026-01-06",
               "third_vendor_date":"2026-01-08",
               "next_vendor_open":str(entry),"third_vendor_close":str(close),
               "next_open_fill_assumed":False,
               "exit_close_fill_assumed":False,
               "T_plus_1_execution_verified":False,
               "trade_return":None,
           }]}
    proxy_file=Path(folder)/"proxy.json"
    proxy_file.write_text(json.dumps(proxy))
    return root,manifest,proxy_file


class BarrierTouchTests(unittest.TestCase):
    @patch("collector.p4_tplus1_barrier_touch.verify",
           return_value={"trade_gate":"BLOCKED","orders":[],
                         "independently_verified_events":1,
                         "independently_verified_forward_ready":1})
    def test_both_barriers_same_day_are_not_filled_in_any_order(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,manifest,proxy=fixture(d)
            r=audit(root,manifest,proxy)
            self.assertEqual(r["status"],
                             "TPLUS1_BARRIER_TOUCHES_NOT_EXECUTABLE_BACKTEST")
            self.assertEqual(r["source_verified_mature_price_pairs"],1)
            self.assertEqual(r["entry_day_touches"]["stop_touched_sell_not_allowed"],1)
            self.assertEqual(r["entry_day_touches"]["target_touched_sell_not_allowed"],1)
            self.assertEqual(r["first_sell_eligible_days_touches"]["both_unknown_order"],1)
            self.assertEqual(r["first_sell_eligible_days_touches"]["first_touch_second_vendor_day"],1)
            self.assertEqual(r["trade_gate"],"BLOCKED")
            self.assertEqual(r["orders"],[])
            self.assertFalse(r["risk_gate_verified"])
            self.assertFalse(r["trade_authorized"])
            self.assertEqual(r["broker_trade_count"],0)
            self.assertTrue(json.dumps(r))
            verified.assert_called_once()

    @patch("collector.p4_tplus1_barrier_touch.verify",
           return_value={"trade_gate":"BLOCKED","orders":[],
                         "independently_verified_events":1,
                         "independently_verified_forward_ready":1})
    def test_gap_below_stop_is_not_assumed_fill(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,manifest,proxy=fixture(d,"gap")
            r=audit(root,manifest,proxy)
            self.assertEqual(r["first_sell_eligible_days_touches"]["stop_only"],1)
            self.assertEqual(r["first_sell_eligible_days_touches"]["gap_open_below_stop"],1)
            self.assertEqual(r["entry_day_touches"]["stop_touched_sell_not_allowed"],0)
            self.assertFalse(r["trade_authorized"])

    @patch("collector.p4_tplus1_barrier_touch.verify",
           return_value={"trade_gate":"BLOCKED","orders":[],
                         "independently_verified_events":1,
                         "independently_verified_forward_ready":1})
    def test_neither_barrier_touched_remains_unscored(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,manifest,proxy=fixture(d,"neither")
            r=audit(root,manifest,proxy)
            self.assertEqual(r["first_sell_eligible_days_touches"]["neither"],1)
            self.assertEqual(r["first_sell_eligible_days_touches"]["target_only"],0)
            self.assertFalse(r["trade_returns_computed"])

    @patch("collector.p4_tplus1_barrier_touch.verify",
           return_value={"trade_gate":"BLOCKED","orders":[],
                         "independently_verified_events":1,
                         "independently_verified_forward_ready":1})
    def test_malicious_or_truncated_price_proxy_rejected(self,verified):
        mutations=(
            lambda p:p.update(trade_gate="OPEN"),
            lambda p:p["orders"].append({"side":"BUY"}),
            lambda p:p["observed_price_pairs"][0].update(next_open_fill_assumed=True),
            lambda p:p["observed_price_pairs"][0].update(trade_return="10"),
            lambda p:p["observed_price_pairs"][0].update(third_vendor_close="12"),
            lambda p:p["observed_price_pairs"][0].update(original_csv_sha256="0"*64),
            lambda p:p["observed_price_pairs"].clear(),
            lambda p:p.update(historical_PIT_verified=True),
            lambda p:p.update(censored_events=1),
            lambda p:p.update(future_vendor_status_blocked=-1),
        )
        for m in mutations:
            with self.subTest(m=m):
                with tempfile.TemporaryDirectory() as d:
                    root,manifest,path=fixture(d)
                    p=json.loads(path.read_text())
                    m(p)
                    path.write_text(json.dumps(p))
                    self.assertEqual(audit(root,manifest,path)["status"],"REJECTED")

    @patch("collector.p4_tplus1_barrier_touch.verify",
           return_value={"trade_gate":"BLOCKED","orders":[],
                         "independently_verified_events":1,
                         "independently_verified_forward_ready":1})
    def test_original_price_tampering_rejected(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,manifest,proxy=fixture(d)
            csv_path=root/"epoch"/"shard_0000"/"sh_600000.csv"
            csv_path.write_text(csv_path.read_text().replace("10.60","12.60"))
            r=audit(root,manifest,proxy)
            self.assertEqual(r["reason"],"ARCHIVED_ORIGINAL_SHA_MISMATCH")

    def test_ceiling_tick_rounding_and_ohlc_ambiguity(self):
        self.assertEqual(barrier(Decimal("10.01")),
                         (Decimal("9.81"),Decimal("10.52")))
        self.assertNotEqual(barrier(Decimal("10.01"))[0],Decimal("9.80"))

    @patch("collector.p4_tplus1_barrier_touch.verify",
           return_value={"trade_gate":"OPEN","orders":[{"side":"BUY"}]})
    def test_independent_attestation_must_be_research_blocked(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,manifest,proxy=fixture(d)
            self.assertEqual(audit(root,manifest,proxy)["reason"],
                             "UNSAFE_INDEPENDENT_ORIGINAL_REPLAY")


if __name__ == "__main__":
    unittest.main()
