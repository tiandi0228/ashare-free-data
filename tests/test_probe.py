"""Offline provider-contract checks: no network, no trading."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.probe import CODES, check_frame, run

class FakeFrame:
    empty = False
    columns = ("日期", "股票代码")
    def __init__(self, code, wrong=False):
        self.code = code
        self.dates = ["2024-10-21", "2024-10-22"]
        if wrong:
            self.dates[1] = "2024-10-21"
    def __len__(self):
        return len(self.dates)
    def __getitem__(self, key):
        if key == "股票代码":
            return [self.code] * 2
        if key == "日期":
            return self.dates
        raise KeyError(key)
    def to_csv(self, index=False):
        return "日期,股票代码\n" + "".join(f"{d},{self.code}\n" for d in self.dates)

class FakeProvider:
    def __init__(self, invalid=False):
        self.calls = []
        self.invalid = invalid
    def stock_zh_a_hist(self, **kwargs):
        self.calls.append(kwargs)
        return FakeFrame(kwargs["symbol"],wrong=self.invalid)

class ProbeTests(unittest.TestCase):
    def test_bounded_probe_blocks_trades(self):
        api = FakeProvider()
        with tempfile.TemporaryDirectory() as tmp:
            rc = run(Path(tmp), api)
            self.assertEqual(rc, 0)
            import json, hashlib
            p = Path(tmp)
            report = json.loads((p / "quality.json").read_text())
            self.assertEqual([x["code"] for x in report["symbols"]],list(CODES))
            self.assertEqual(report["logical_sdk_calls"],3)
            self.assertFalse(report["full_market_coverage_verified"])
            self.assertFalse(report["strategy_validated"])
            self.assertEqual(report["trade_gate"],"BLOCKED")
            self.assertEqual(report["orders"],[])
            self.assertEqual(len(api.calls),3)
            for entry in report["symbols"]:
                raw=(p / (entry["code"]+".csv")).read_bytes()
                self.assertEqual(entry["sha256"],hashlib.sha256(raw).hexdigest())
    def test_duplicate_dates_fail_closed(self):
        api=FakeProvider(invalid=True)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(Path(tmp),api),2)
            self.assertEqual(len(api.calls),3)
            self.assertEqual(list(Path(tmp).glob("*.csv")),[])
    def test_identity_mismatch(self):
        with self.assertRaises(ValueError):
            check_frame(FakeFrame("600001"),"600000")

if __name__ == "__main__":
    unittest.main()
