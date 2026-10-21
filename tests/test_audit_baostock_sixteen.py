"""Offline integrity tests for two independent original-source research artifacts."""
import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from collector.audit_baostock_sixteen import (
    EXPECTED_603019_HALTS, validate,
)
from collector.baostock_batch import CAP, FIELDS

CODES = [
    "sh.600000", "sz.000001", "sh.601398", "sz.002204",
    "sh.603019", "sz.000651", "sh.601975", "sh.600256",
    "sz.002733", "sh.601208", "sz.002565", "sz.002149",
    "sz.002580", "sh.600026", "sh.601872", "sh.600028",
]

def make_case(root):
    root = Path(root)
    manifest_file = root / "manifest.txt"
    manifest_file.write_text(chr(10).join(CODES) + chr(10))
    manifest_sha = hashlib.sha256(manifest_file.read_bytes()).hexdigest()
    days = [(date(2024, 10, 21) + timedelta(days=i)).isoformat() for i in range(485)]
    roots = (root / "first", root / "second")
    for idx, folder in enumerate(roots):
        folder.mkdir()
        issuer_receipts = []
        for code in CODES[idx * CAP:(idx+1) * CAP]:
            lines = [",".join(FIELDS)]
            halted = set(EXPECTED_603019_HALTS) if code == "sh.603019" else set()
            for day in days:
                trade = "0" if day in halted else "1"
                lines.append(",".join([day, code, "1", "1", "1", "1", "10", "20", "3", trade]))
            raw = (chr(10).join(lines) + chr(10)).encode()
            (folder / (code.replace(".", "_") + ".csv")).write_bytes(raw)
            issuer_receipts.append({
                "code": code, "status": "OBSERVED_UNVERIFIED", "rows": 485,
                "tradable_rows": 485 - len(halted),
                "suspended_status_rows": len(halted),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
        receipt = {
            "phase": "BAOSTOCK_FREE_BOUNDED_BATCH",
            "status": "OBSERVED_SUBSET_UNVERIFIED",
            "batch_index": idx, "batch_count": 2,
            "manifest_sha256": manifest_sha, "issuer_count": CAP,
            "login_attempts": 1, "query_attempts": CAP,
            "paid_api_calls": 0, "trade_gate": "BLOCKED",
            "orders": [], "executable_candidates": [],
            "official_exchange_authenticated": False,
            "historical_point_in_time_universe_verified": False,
            "results": issuer_receipts,
        }
        (folder / "quality.json").write_text(json.dumps(receipt))
    return manifest_file, roots[0], roots[1]

class SixteenAuditTests(unittest.TestCase):
    def test_complete_two_shard_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, first, second = make_case(tmp)
            report = validate(manifest, first, second, 101, 102)
            self.assertEqual(report["issuer_count"], 16)
            self.assertEqual(report["original_source_rows"], 16 * 485)
            self.assertEqual(report["trade_status_0_rows"], 10)
            self.assertEqual(report["trade_status_1_rows"], 16 * 485 - 10)
            self.assertEqual(report["trade_gate"], "BLOCKED")
            self.assertFalse(report["market_wide_backfill_complete"])
    def test_tampering_one_original_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, first, second = make_case(tmp)
            source = first / "sh_600000.csv"
            source.write_bytes(source.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                validate(manifest, first, second, 101, 102)
    def test_swapped_shards_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, first, second = make_case(tmp)
            with self.assertRaisesRegex(ValueError, "receipt is not eligible"):
                validate(manifest, second, first, 101, 102)
    def test_repeated_run_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, first, second = make_case(tmp)
            with self.assertRaisesRegex(ValueError, "run identities"):
                validate(manifest, first, second, 101, 101)
    def test_missing_halt_status_is_rejected_even_if_rehashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, first, second = make_case(tmp)
            source = first / "sh_603019.csv"
            text = source.read_text()
            text = text.replace("2025-05-26,sh.603019,1,1,1,1,10,20,3,0",
                                "2025-05-26,sh.603019,1,1,1,1,10,20,3,1")
            source.write_text(text)
            receipt_path = first / "quality.json"
            receipt = json.loads(receipt_path.read_text())
            row = next(x for x in receipt["results"] if x["code"] == "sh.603019")
            row["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            row["tradable_rows"] += 1
            row["suspended_status_rows"] -= 1
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "halt dates differ"):
                validate(manifest, first, second, 101, 102)

if __name__ == "__main__":
    unittest.main()
