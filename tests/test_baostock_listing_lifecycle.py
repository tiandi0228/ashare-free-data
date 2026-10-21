"""Offline-only lifecycle contract tests."""
import json
import tempfile
import unittest
from pathlib import Path
from collector.baostock_listing_lifecycle import audit_rows, capture, FIELDS

ROWS = [
    ["sh.600000", "浦发银行", "2001-01-01", "", "1", "1"],
    ["sz.000001", "平安银行", "1998-01-01", "", "1", "1"],
    ["sh.601001", "已退市", "2010-01-01", "2026-01-01", "1", "0"],
    ["sz.300750", "创业板", "2018-01-01", "", "1", "1"],
    ["sh.000001", "指数", "1991-01-01", "", "2", "1"],
]
class Result:
    error_code = "0"
    fields = list(FIELDS)
    def __init__(self, rows):
        self.rows, self.i = rows, 0
    def next(self):
        if self.i >= len(self.rows): return False
        self.i += 1
        return True
    def get_row_data(self):
        return self.rows[self.i - 1]
class Provider:
    def __init__(self, rows, failed=False):
        self.rows, self.failed = rows, failed
        self.login_count = self.query_count = self.logout_count = 0
    def login(self):
        self.login_count += 1
        return type("Auth", (), {"error_code": "999" if self.failed else "0"})()
    def query_stock_basic(self):
        self.query_count += 1
        return Result(self.rows)
    def logout(self):
        self.logout_count += 1

class LifecycleTests(unittest.TestCase):
    def test_historical_vendor_interval_not_pit(self):
        main, dates = audit_rows(ROWS, min_mainboard=1)
        self.assertEqual(len(main), 3)
        self.assertEqual([x["candidate_issuer_count_from_vendor_dates"] for x in dates], [3, 2])
        self.assertEqual(dates[0]["vendor_currently_delisted_but_candidate_at_date"], 1)
        self.assertFalse(dates[0]["source_datetime_proves_historical_knowledge"])
    def test_original_sha_and_blocked_no_trading(self):
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            api = Provider(ROWS)
            self.assertEqual(capture(root, api, minimum=1), 0)
            self.assertEqual((api.login_count, api.query_count, api.logout_count), (1, 1, 1))
            q = json.loads((Path(root) / "quality.json").read_text())
            self.assertFalse(q["historical_point_in_time_universe_verified"])
            self.assertEqual(q["trade_gate"], "BLOCKED")
            self.assertEqual(q["orders"], [])
            self.assertEqual(hashlib.sha256((Path(root) / q["source_csv_name"]).read_bytes()).hexdigest(), q["source_csv_sha256"])
    def test_login_failure_avoids_any_query(self):
        with tempfile.TemporaryDirectory() as root:
            api = Provider(ROWS, True)
            self.assertEqual(capture(root, api, minimum=1), 2)
            self.assertEqual((api.login_count, api.query_count, api.logout_count), (1, 0, 0))
            q = json.loads((Path(root) / "quality.json").read_text())
            self.assertEqual(q["provider_login_code"], "999")
    def test_reject_duplicate_and_unknown_delist_boundary(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit_rows(ROWS + [ROWS[0]], min_mainboard=1)
        with self.assertRaisesRegex(ValueError, "no dated boundary"):
            audit_rows([["sh.600000", "退市", "2000-01-01", "", "1", "0"]], min_mainboard=1)
        with self.assertRaisesRegex(ValueError, "precedes"):
            audit_rows([["sh.600000", "退市", "2020-01-01", "2019-01-01", "1", "0"]], min_mainboard=1)
    def test_no_trust_in_tiny_source(self):
        with self.assertRaisesRegex(ValueError, "Implausibly"):
            audit_rows(ROWS, min_mainboard=1000)
if __name__ == "__main__":
    unittest.main()
