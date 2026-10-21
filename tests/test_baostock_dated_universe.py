"""No-network Baostock historical roster contract and fail-closed tests."""
import json
import tempfile
import unittest
from pathlib import Path

from collector.baostock_dated_universe import DATES, capture, inspect_rows, MAINBOARD


class Response:
    error_code = "0"
    fields = ["code", "tradeStatus", "code_name"]

    def __init__(self, rows):
        self.rows = rows
        self.index = -1

    def next(self):
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self):
        return self.rows[self.index]


class Source:
    def __init__(self, wrong_halt=False, login_fail=False, duplicate=False):
        self.calls = []
        self.logouts = 0
        self.wrong_halt = wrong_halt
        self.login_fail = login_fail
        self.duplicate = duplicate

    def login(self):
        return type("Auth", (), {"error_code": "999" if self.login_fail else "0"})()

    def logout(self):
        self.logouts += 1

    def query_all_stock(self, day):
        self.calls.append(day)
        rows = [
            ["sh.600000", "1", "浦发银行"],
            ["sz.000001", "1", "平安银行"],
            ["sh.603019", "1" if self.wrong_halt or day != DATES[0] else "0", "中科曙光"],
            ["sz.300750", "1", "创业板测试"],
            ["sh.688001", "1", "科创板测试"],
        ]
        if self.duplicate:
            rows.append(rows[0])
        return Response(rows)


class Tests(unittest.TestCase):
    def test_mainboard_prefix_filter_not_official_pool(self):
        self.assertTrue(MAINBOARD.fullmatch("sh.605001"))
        self.assertTrue(MAINBOARD.fullmatch("sz.003001"))
        self.assertFalse(MAINBOARD.fullmatch("sh.688001"))
        self.assertFalse(MAINBOARD.fullmatch("sz.300750"))
        self.assertEqual(len(inspect_rows([
            ["sh.600000", "1", "浦发银行"],
            ["sz.300750", "1", "创业板测试"],
        ], minimum=1)), 1)

    def test_two_dated_snapshots_and_no_trade_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Source()
            self.assertEqual(capture(tmp, source, minimum=1), 0)
            r = json.loads((Path(tmp) / "quality.json").read_text())
            self.assertEqual(source.calls, list(DATES))
            self.assertEqual(source.logouts, 1)
            self.assertEqual(r["logical_query_attempts"], 2)
            self.assertEqual(r["trade_gate"], "BLOCKED")
            self.assertEqual(r["orders"], [])
            self.assertFalse(r["point_in_time_issuer_membership_verified"])
            self.assertEqual(r["date_results"][0]["known_halt_case_status"], "0")
            self.assertEqual(r["date_results"][0]["mainboard_prefix_rows"], 3)
            import hashlib
            for row in r["date_results"]:
                raw = (Path(tmp) / row["original_csv_file"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row["original_csv_sha256"])

    def test_issuer_event_disagreement_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Source(wrong_halt=True)
            self.assertEqual(capture(tmp, source, minimum=1), 2)
            r = json.loads((Path(tmp) / "quality.json").read_text())
            self.assertEqual(r["status"], "BLOCKED_PARTIAL")
            self.assertEqual(r["date_results"][0]["status"], "ERROR")
            self.assertEqual(r["date_results"][0]["error_type"], "ValueError")
            self.assertEqual(source.calls, list(DATES))
            self.assertEqual(r["orders"], [])

    def test_duplicate_issuer_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Source(duplicate=True)
            self.assertEqual(capture(tmp, source, minimum=1), 2)
            self.assertTrue(all(x["status"] == "ERROR" for x in
                                json.loads((Path(tmp) / "quality.json").read_text())["date_results"]))

    def test_login_failure_no_snapshot_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Source(login_fail=True)
            self.assertEqual(capture(tmp, source, minimum=1), 2)
            self.assertEqual(source.calls, [])
            self.assertEqual(source.logouts, 0)

    def test_empty_and_non_mainboard_fail_closed(self):
        with self.assertRaises(ValueError):
            inspect_rows([], minimum=1)
        with self.assertRaises(ValueError):
            inspect_rows([["sh.600000", "2", "浦发银行"]], minimum=1)


if __name__ == "__main__":
    unittest.main()
