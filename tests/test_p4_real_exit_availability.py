"""Vendor-suspension exit-day regression tests: never infer real fills."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collector.p4_real_exit_availability import audit

CODE = "sh.600150"
HEADER = "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus"


def fixture(root, *, target_status="0"):
    folder = Path(root) / "epoch" / "shard_0000"
    folder.mkdir(parents=True)
    # Monday entry, Thursday D+3 candidate exit. Thursday source status may
    # show a suspended session with blank vendor turnover (real BaoStock form).
    target_turnover = ",," if target_status == "0" else ",100,3850,"
    if target_status == "0":
        target = f"2025-08-14,{CODE},38.5,38.5,38.5,38.5,,,3,0"
    else:
        target = f"2025-08-14,{CODE},38.5,38.5,38.5,38.5,100,3850,3,1"
    rows = [
        HEADER,
        f"2025-08-11,{CODE},38.5,38.5,38.5,38.5,100,3850,3,1",
        target,
    ]
    raw = ("\n".join(rows) + "\n").encode("utf-8")
    (folder / "sh_600150.csv").write_bytes(raw)
    (folder / "quality.json").write_text(json.dumps({
        "status": "OBSERVED_SUBSET_UNVERIFIED",
        "trade_gate": "BLOCKED",
        "orders": [],
        "historical_point_in_time_universe_verified": False,
        "issuer_count": 1,
        "results": [{
            "code": CODE,
            "status": "OBSERVED_UNVERIFIED",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": 2,
            "tradable_rows": 1 if target_status == "0" else 2,
            "suspended_status_rows": 1 if target_status == "0" else 0,
        }],
    }), encoding="utf-8")


class Tests(unittest.TestCase):
    def test_no_real_archive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                audit(d)

    def test_vendor_suspended_target_exit_is_not_a_fill(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, target_status="0")
            result = audit(d, cutoff="2025-08-10")
            self.assertEqual(result["target_vendor_suspended"], 1)
            self.assertEqual(result["target_vendor_active"], 0)
            self.assertEqual(result["vendor_halt_crosscheck_queue"][0]["code"], CODE)
            self.assertEqual(result["vendor_halt_crosscheck_queue"][0]["target_exit_date"], "2025-08-14")
            self.assertFalse(result["vendor_halt_crosscheck_queue"][0]["official_halt_verified"])
            self.assertEqual(result["fills_verified"], 0)
            self.assertEqual(result["trade_gate"], "BLOCKED")
            self.assertEqual(result["orders"], [])

    def test_vendor_active_target_still_does_not_prove_fill(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, target_status="1")
            result = audit(d, cutoff="2025-08-10")
            self.assertGreaterEqual(result["target_vendor_active"], 1)
            self.assertTrue(result["vendor_active_does_not_prove_fill"])
            self.assertFalse(result["halt_status_independently_authenticated"])
            self.assertEqual(result["fills_verified"], 0)
            self.assertEqual(result["executable_candidates"], [])
            self.assertEqual(result["trade_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
