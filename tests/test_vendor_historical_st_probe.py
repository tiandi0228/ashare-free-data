"""Synthetic status fixtures for the limited vendor ST survey (not official)."""
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from collector.vendor_historical_st_probe import CODES, FIELDS, capture, validate


def data_for(code):
    start = date(2025, 5, 20)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(27)]
    if code == "sh.600421":
        dates += ["2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25"]
    rows=[]
    for day in dates:
        halt = (code=="sh.603019" and day=="2025-05-26") or (
            code=="sh.600421" and day in ("2026-06-23","2026-06-24","2026-06-25")
        )
        rows.append([day,code,"0" if halt else "1","0" if not halt else ""])
    return rows


class Result:
    error_code="0"
    fields=FIELDS
    def __init__(self,code,swap=False):
        self.rows=data_for(code)
        if swap:
            self.rows[0][3] = "2"
        self.index=0
    def next(self):
        if self.index >= len(self.rows):
            return False
        self.index += 1
        return True
    def get_row_data(self):
        return self.rows[self.index-1]


class FakeProvider:
    def __init__(self,bad=False):
        self.bad=bad
        self.calls=[]
        self.logouts=0
    def login(self):
        return type("L",(),{"error_code":"0"})()
    def logout(self):
        self.logouts+=1
    def query_history_k_data_plus(self,code,**kwargs):
        self.calls.append((code,kwargs))
        return Result(code,swap=self.bad and code=="sh.600421")


class VendorSTProbeTests(unittest.TestCase):
    def test_frozen_dates_and_issuer_st_halt_semantics(self):
        for code in CODES:
            raw,q=validate(code,data_for(code))
            self.assertGreater(q["vendor_ST_0_rows"],20)
            self.assertEqual(q["vendor_ST_1_rows"],0)
            self.assertEqual(q["is_exchange_signed_historical_ST"],False)
            self.assertEqual(q["original_csv_sha256"],hashlib.sha256(raw).hexdigest())
        self.assertEqual(CODES,("sh.600421","sh.603019"))

    def test_two_issuer_source_capture_research_only(self):
        with tempfile.TemporaryDirectory() as root:
            p=FakeProvider()
            self.assertEqual(capture(root,p),0)
            self.assertEqual(len(p.calls),2)
            self.assertEqual(p.logouts,1)
            q=json.loads((Path(root)/"quality.json").read_text())
            self.assertEqual(q["status"],"TWO_ISSUER_VENDOR_ST_OBSERVED_NOT_OFFICIAL")
            self.assertFalse(q["full_market_ST_halt_delist_complete"])
            self.assertFalse(q["source_exchange_authenticated"])
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertEqual(q["orders"],[])
            self.assertEqual(q["executable_candidates"],[])
            self.assertEqual(q["paid_api_calls"],0)

    def test_vendor_risk_1_on_active_is_an_observation_not_authority(self):
        rows=data_for("sh.603019")
        rows[2][3]="1"
        _,q=validate("sh.603019",rows)
        self.assertEqual(q["vendor_ST_1_rows"],1)
        self.assertFalse(q["is_exchange_signed_historical_ST"])

    def test_unknown_risk_active_day_rejected(self):
        rows=data_for("sh.603019")
        rows[1][3]=""
        with self.assertRaisesRegex(ValueError,"Unverifiable vendor ST"):
            validate("sh.603019",rows)

    def test_known_halt_and_final_day_guard(self):
        rows=data_for("sh.603019")
        for r in rows:
            if r[0]=="2025-05-26":
                r[2]="1"
                r[3]="0"
        with self.assertRaisesRegex(ValueError,"Known 603019"):
            validate("sh.603019",rows)
        rows=data_for("sh.600421")
        rows[-1][2]="1"
        rows[-1][3]="0"
        with self.assertRaisesRegex(ValueError,"Known 600421"):
            validate("sh.600421",rows)

    def test_partial_failure_cannot_certify(self):
        with tempfile.TemporaryDirectory() as root:
            p=FakeProvider(bad=True)
            self.assertEqual(capture(root,p),2)
            q=json.loads((Path(root)/"quality.json").read_text())
            self.assertEqual(q["status"],"BLOCKED_PARTIAL")
            self.assertEqual(q["logical_issuer_queries"],2)
            self.assertEqual(q["issuer_results"][0]["status"],"ERROR")
            self.assertEqual(q["issuer_results"][1]["status"],"OBSERVED_VENDOR_ST_UNVERIFIED")
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertEqual(q["orders"],[])


if __name__ == "__main__":
    unittest.main()
