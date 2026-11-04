"""3-to-5 post-entry vendor-session data & Friday T+1 conflict guard."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.p4_three_to_five_vendor_horizon import audit


def fixture(folder, mode="full", start="2026-01-05"):
    # Monday signal, Tuesday prospective entry; Friday is 3 vendor
    # observations AFTER entry. This does not provide a trading calendar.
    dates = [
        "2026-01-05", "2026-01-06", "2026-01-07",
        "2026-01-08", "2026-01-09", "2026-01-12",
        "2026-01-13",
    ]
    if start == "thursday":
        # Thursday signal, Friday entry: impossible to clear same Friday T+1.
        dates = ["2026-01-08", "2026-01-09", "2026-01-12",
                 "2026-01-13", "2026-01-14", "2026-01-15",
                 "2026-01-16"]
    if start == "wednesday":
        # Wednesday signal, Thursday entry; Friday at +1, before +3 minimum.
        dates = ["2026-01-07", "2026-01-08", "2026-01-09",
                 "2026-01-12", "2026-01-13", "2026-01-14",
                 "2026-01-15"]
    if mode == "censored":
        dates = dates[:4]  # signal + 3 vendor days: old P4 maturity only
    rows = []
    for i, d in enumerate(dates):
        status = "0" if ((mode == "halt" and i == 5) or
                         (mode == "friday_halt" and i == 4)) else "1"
        rows.append((d,"10.00","10.40","9.80","10.05",status))
    root = Path(folder)/"raw"
    folder_shard = root/"epoch"/"shard_0000"
    folder_shard.mkdir(parents=True, exist_ok=True)
    code="sh.600000"
    raw = ("date,code,open,high,low,close,volume,amount,adjustflag,tradestatus\n"+
           "".join(f"{day},{code},{o},{h},{lo},{cl},100,1000,3,{status}\n"
                   for day,o,h,lo,cl,status in rows)).encode()
    (folder_shard/"sh_600000.csv").write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    (folder_shard/"quality.json").write_text(json.dumps(
        {"results":[{"code":code,"sha256":digest}]}))
    event={
        "issuer":code, "signal_completed_date":dates[0],
        "source_csv_sha256":digest,
        "three_future_observed_dates":dates[1:4],
        "three_future_vendor_tradable":True,"fill_assumed":False,
    }
    manifest=Path(folder)/"manifest.json"
    manifest.write_text(json.dumps({
        "phase":"P4_REAL_VENDOR_MA20_FORWARD_OBSERVATION",
        "cutoff_inclusive":"2025-12-31",
        "archive_commit_sha":"a"*40,
        "nonoverlapping_three_observation_crossing_events":1,
        "nonoverlapping_event_evidence":[event],
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "trade_gate":"BLOCKED", "orders":[],"executable_candidates":[],
    }))
    proxy=Path(folder)/"proxy.json"
    proxy.write_text(json.dumps({
        "phase":"P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES",
        "status":"OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST",
        "archive_commit_sha":"a"*40,
        "holdout_cutoff_inclusive":"2025-12-31",
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "actionable_buy_signals":[],
        "fills_assumed":0,"trades_assumed":0,
        "historical_PIT_verified":False,
        "historical_OOS_validated":False,
        "strategy_backtest_certified":False,
        "verified_nonoverlap_events":1,
        "observed_next_open_to_third_close":1,
        "observed_price_pairs":[{
            "issuer":code,"signal_known_after_close_date":dates[0],
            "original_csv_sha256":digest,
            "next_vendor_date":dates[1],
            "third_vendor_date":dates[3],
            "next_vendor_open":"10.00",
            "third_vendor_close":"10.05",
            "next_open_fill_assumed":False,
            "exit_close_fill_assumed":False,
            "T_plus_1_execution_verified":False,
            "trade_return":None,
        }]
    }))
    return root, manifest, proxy


def independent():
    return {"trade_gate":"BLOCKED","orders":[],
            "independently_verified_events":1,
            "independently_verified_forward_ready":1}


class HorizonTests(unittest.TestCase):
    @patch("collector.p4_three_to_five_vendor_horizon.verify",
           side_effect=lambda *a: independent())
    def test_full_five_vendor_session_observations_with_friday_at_three(self, proof):
        with tempfile.TemporaryDirectory() as folder:
            r=audit(*fixture(folder))
            self.assertEqual(r["status"],
                "THREE_TO_FIVE_VENDOR_COVERAGE_ONLY_NO_BACKTEST")
            self.assertEqual(r["hypothetical_entry_price_pairs"],1)
            for horizon in ("3","4","5"):
                self.assertEqual(r["horizon_sessions_after_hypothetical_entry"]
                                 [horizon]["vendor_observations_available_not_fills"],1)
            self.assertEqual(r["friday_mandatory_exit_conflicts"]
                             ["FRIDAY_AT_THREE_TO_FIVE_VENDOR_SESSIONS"],1)
            self.assertEqual(r["friday_and_minimum_holding_compatibility_research"]
                             ["OBSERVED_FRIDAY_WINDOW_ONLY_NOT_TRADABLE"],1)
            self.assertEqual(
                r["samples"][0]["first_friday_vendor_date_unverified"],
                "2026-01-09")
            self.assertEqual(
                r["samples"][0]["friday_minimum_holding_compatibility"],
                "OBSERVED_FRIDAY_WINDOW_ONLY_NOT_TRADABLE")
            self.assertFalse(r["pre_entry_friday_policy_trade_permission_certified"])
            self.assertFalse(r["lookahead_data_used_for_entry_screening"])
            self.assertFalse(r["prospective_friday_calendar_rule_frozen"])
            self.assertEqual(r["samples"][0]["vendor_day_after_entry_3_4_5"],
                             {"3":"2026-01-09","4":"2026-01-12",
                              "5":"2026-01-13"})
            self.assertFalse(r["historical_PIT_verified"])
            self.assertFalse(r["strategy_backtest_certified"])
            self.assertFalse(r["trading_calendar_certified"])
            self.assertFalse(r["strategy_returns_computed"])
            self.assertEqual(r["orders"],[])
            self.assertEqual(r["trade_gate"],"BLOCKED")

    @patch("collector.p4_three_to_five_vendor_horizon.verify",
           side_effect=lambda *a: independent())
    def test_prior_three_row_research_cannot_certify_three_day_hold(self, proof):
        with tempfile.TemporaryDirectory() as folder:
            r=audit(*fixture(folder,mode="censored"))
            self.assertEqual(r["status"],
                "THREE_TO_FIVE_VENDOR_COVERAGE_ONLY_NO_BACKTEST")
            for horizon in ("3","4","5"):
                self.assertEqual(r["horizon_sessions_after_hypothetical_entry"]
                                 [horizon]["insufficient_original_rows_censored"],1)
            self.assertEqual(r["friday_mandatory_exit_conflicts"]
                             ["FIRST_FRIDAY_NOT_OBSERVED_IN_BOUNDED_WINDOW"],1)
            self.assertEqual(
                r["friday_and_minimum_holding_compatibility_research"][
                    "UNKNOWN_FIRST_FRIDAY_NOT_IN_ARCHIVE_WINDOW"], 1)

    @patch("collector.p4_three_to_five_vendor_horizon.verify",
           side_effect=lambda *a: independent())
    def test_untradable_vendor_row_blocks_horizon_not_assumed_exit(self, proof):
        with tempfile.TemporaryDirectory() as folder:
            r=audit(*fixture(folder,mode="halt"))
            self.assertEqual(r["horizon_sessions_after_hypothetical_entry"]
                             ["3"]["vendor_observations_available_not_fills"],1)
            for horizon in ("4","5"):
                self.assertEqual(r["horizon_sessions_after_hypothetical_entry"]
                                 [horizon]["vendor_status_blocked"],1)
            self.assertEqual(r["broker_fills_confirmed"],0)
            self.assertEqual(
                r["friday_and_minimum_holding_compatibility_research"][
                    "OBSERVED_FRIDAY_WINDOW_ONLY_NOT_TRADABLE"],1)

    @patch("collector.p4_three_to_five_vendor_horizon.verify",
           side_effect=lambda *a: independent())
    def test_friday_vendor_halt_cannot_be_mislabeled_compatible(self, proof):
        with tempfile.TemporaryDirectory() as folder:
            r=audit(*fixture(folder,mode="friday_halt"))
            self.assertEqual(r["status"],
                             "THREE_TO_FIVE_VENDOR_COVERAGE_ONLY_NO_BACKTEST")
            self.assertEqual(
                r["friday_mandatory_exit_conflicts"][
                    "FRIDAY_AT_THREE_TO_FIVE_VENDOR_SESSIONS"],1)
            self.assertEqual(
                r["friday_and_minimum_holding_compatibility_research"][
                    "UNKNOWN_VENDOR_STATUS_BEFORE_FRIDAY"],1)
            self.assertEqual(r["horizon_sessions_after_hypothetical_entry"]
                             ["3"]["vendor_status_blocked"],1)
            self.assertEqual(r["orders"],[])
            self.assertEqual(r["trade_gate"],"BLOCKED")

    @patch("collector.p4_three_to_five_vendor_horizon.verify",
           side_effect=lambda *a: independent())
    def test_entry_friday_and_early_friday_are_distinct(self, proof):
        for start, category, screening in (
            ("thursday","ENTRY_FRIDAY_TPLUS1_CANNOT_CLEAR_SAME_FRIDAY",
             "NO_GO_ENTRY_FRIDAY_TPLUS1"),
            ("wednesday","FRIDAY_BEFORE_MINIMUM_THREE_VENDOR_SESSIONS",
             "NO_GO_MINIMUM_HOLD_VS_FRIDAY"),
        ):
            with self.subTest(start=start):
                with tempfile.TemporaryDirectory() as folder:
                    r=audit(*fixture(folder,start=start))
                    self.assertEqual(r["friday_mandatory_exit_conflicts"]
                                     [category],1)
                    self.assertEqual(
                        r["friday_and_minimum_holding_compatibility_research"]
                         [screening],1)
                    self.assertFalse(
                        r["pre_entry_friday_policy_trade_permission_certified"])
                    self.assertFalse(r["historical_PIT_verified"])
                    self.assertEqual(r["trade_gate"],"BLOCKED")

    @patch("collector.p4_three_to_five_vendor_horizon.verify",
           side_effect=lambda *a: independent())
    def test_unsafe_mutations_and_modified_archive_rejected(self, proof):
        mutations = [
            ("proxy",lambda d:d.update(trade_gate="OPEN")),
            ("proxy",lambda d:d["orders"].append({"side":"BUY"})),
            ("proxy",lambda d:d["observed_price_pairs"][0].update(
                next_open_fill_assumed=True)),
            ("proxy",lambda d:d["observed_price_pairs"][0].update(
                next_vendor_open="11")),
            ("proxy",lambda d:d["observed_price_pairs"][0].update(
                original_csv_sha256="c"*64)),
            ("proxy",lambda d:d.update(observed_next_open_to_third_close=2)),
            ("manifest",lambda d:d.update(historical_PIT_verified=True)),
            ("manifest",lambda d:d["nonoverlapping_event_evidence"][0]
              .update(source_csv_sha256="c"*64)),
        ]
        for path, mutate in mutations:
            with self.subTest(path=path,mutate=mutate):
                with tempfile.TemporaryDirectory() as folder:
                    root, manifest, proxy=fixture(folder)
                    target = manifest if path=="manifest" else proxy
                    data=json.loads(target.read_text())
                    mutate(data)
                    target.write_text(json.dumps(data))
                    r=audit(root,manifest,proxy)
                    self.assertEqual(r["status"],"REJECTED")
                    self.assertEqual(r["trade_gate"],"BLOCKED")
                    self.assertEqual(r["orders"],[])

    @patch("collector.p4_three_to_five_vendor_horizon.verify",
           side_effect=lambda *a: independent())
    def test_real_csv_sha_tampering_refused(self, proof):
        with tempfile.TemporaryDirectory() as folder:
            root,manifest,proxy=fixture(folder)
            filepath=root/"epoch"/"shard_0000"/"sh_600000.csv"
            filepath.write_text(filepath.read_text().replace("10.40","12.40"))
            r=audit(root,manifest,proxy)
            self.assertEqual(r["status"],"REJECTED")
            self.assertEqual(r["reason"],"PRICE_ORIGINAL_SHA_CHANGED")


if __name__=="__main__":
    unittest.main()
