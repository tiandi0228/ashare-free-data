"""Offline integrity checks for the eight observed early-only research receipts.

This audits committed metadata only. It is NOT independent replay of vendor
source bytes and must never unlock point-in-time or trading gates.
"""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest

REPORT = Path(__file__).resolve().parents[1] / "reports/p1_early_only_8_historical_research_20261022.json"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CODE = re.compile(r"sh\.6[0-9]{5}\Z")


def audit_receipt(receipt):
    q = receipt["source_quality"]
    rows = q["results"]
    assert receipt["capture_run_id"] == 39699471799
    assert receipt["run_conclusion"] == "success"
    assert q["status"] == "EIGHT_HISTORICAL_EARLY_ONLY_VENDOR_SAMPLES_OBSERVED_PIT_BLOCKED"
    assert q["issuer_count"] == q["logical_source_queries"] == q["source_observed_issuers"] == 8
    assert len(rows) == len(q["issuer_codes"]) == 8
    assert len(set(q["issuer_codes"])) == 8
    assert all(CODE.fullmatch(c) for c in q["issuer_codes"])
    assert [r["code"] for r in rows] == q["issuer_codes"]
    assert all(r["status"] == "VENDOR_HISTORY_OBSERVED_NOT_PIT" for r in rows)
    assert all(HEX64.fullmatch(r["original_source_sha256"]) for r in rows)
    assert all(r["original_source_rows"] == r["vendor_trade_status_1_rows"] +
               r["vendor_trade_status_0_rows"] and
               r["original_source_rows"] > 0 and
               r["first_vendor_row_date"] <= r["last_vendor_trade_status_1_date"] <=
               r["last_vendor_row_date"] for r in rows)
    assert sum(r["original_source_rows"] for r in rows) == q["source_observed_rows"] == 2444
    assert receipt["total_research_issuer_samples_with_history"] == 32
    assert receipt["vendor_total_rows_for_all_32"] == 14007
    assert q["selection_lineage"]["early_only_vendor_issuer_count"] == 32
    assert q["selection_lineage"]["not_a_historical_asof_eligible_universe"] is True
    assert q["retrospective_selection_uses_future_information"] is True
    assert q["valid_for_backtest_membership_asof_early_day"] is False
    assert q["official_delisting_state_verified"] is False
    assert q["official_historical_PIT_universe_verified"] is False
    assert receipt["original_issuer_source_data_durably_replayable"] is False
    assert receipt["earlier_24_independently_sha_replayed_but_new_8_not_replayed"] is True
    assert receipt["raw_vendor_bar_CSV_redistributed"] is False
    assert q["source_original_bytes_durably_archived"] is False
    assert receipt["trade_gate"] == q["trade_gate"] == "BLOCKED"
    assert receipt["orders"] == q["orders"] == []
    assert receipt["executable_candidates"] == q["executable_candidates"] == []
    assert receipt["candidate_universe"] == q["candidate_universe"] == []
    assert receipt["paid_api_calls"] == q["paid_api_calls"] == 0
    expiry = datetime.fromisoformat(receipt["capture_receipt_artifact_expires_at_utc"].replace("Z", "+00:00"))
    assert expiry.tzinfo is not None
    return {"issuer_count": 8, "rows": 2444, "archive_replay_ready": False,
            "trade_gate": "BLOCKED", "receipt_expiration": expiry.isoformat()}


class EarlyOnlyCommittedReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_committed_receipt_conservation_and_fail_closed(self):
        self.assertEqual(audit_receipt(self.data)["rows"], 2444)

    def test_issuer_row_count_tamper(self):
        v = copy.deepcopy(self.data)
        v["source_quality"]["results"][0]["original_source_rows"] += 1
        with self.assertRaises(AssertionError):
            audit_receipt(v)

    def test_reject_false_official_pit_promotion(self):
        v = copy.deepcopy(self.data)
        v["source_quality"]["official_historical_PIT_universe_verified"] = True
        with self.assertRaises(AssertionError):
            audit_receipt(v)

    def test_reject_false_original_archive(self):
        v = copy.deepcopy(self.data)
        v["original_issuer_source_data_durably_replayable"] = True
        with self.assertRaises(AssertionError):
            audit_receipt(v)

    def test_reject_trade_gate_open(self):
        v = copy.deepcopy(self.data)
        v["trade_gate"] = "OPEN"
        with self.assertRaises(AssertionError):
            audit_receipt(v)


if __name__ == "__main__":
    unittest.main()
