"""Freeze 24 original source identities and validate 8-query replay without trades."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from collector.baostock_batch import FIELDS, manifest
from collector.reacquire_24_pilot import source_index, compare_source, run

ROOT=Path(__file__).resolve().parents[1]


def history(code):
    if code=="sh.600421":
        dates=[("2026-05-26","0"),("2026-06-01","1"),("2026-06-22","1"),
               ("2026-06-23","0"),("2026-06-24","0"),("2026-06-25","0")]
    elif code=="sh.603019":
        dates=[("2025-05-26","0"),("2025-06-01","1")]
    else:
        dates=[("2026-05-20","1"),("2026-05-21","1")]
    return [[date,code,"10.00","10.00","10.00","10.00",
             "100","1000","3",status] for date,status in dates]


def source_sha(code):
    rows=history(code)
    raw=(",".join(FIELDS)+"\n"+
         "".join(",".join(row)+"\n" for row in rows)).encode()
    return hashlib.sha256(raw).hexdigest()


class FakeResult:
    error_code="0"
    fields=FIELDS
    def __init__(self,code,drift=False):
        self.rows=history(code);self.i=0
        if drift:
            self.rows[-1][2:6]=["11.00"]*4
    def next(self):
        self.i+=1
        return self.i<=len(self.rows)
    def get_row_data(self):
        return self.rows[self.i-1]


class FakeClient:
    def __init__(self,drift=False,login_failure=False):
        self.queries=[];self.logouts=0
        self.drift=drift;self.login_failure=login_failure
    def login(self):
        return type("Login",(),{"error_code":"400" if self.login_failure else "0"})()
    def logout(self):
        self.logouts+=1
    def query_history_k_data_plus(self,code,**kwargs):
        self.queries.append((code,kwargs))
        return FakeResult(code,drift=self.drift and code=="sh.600000")


class Frozen24ReacquireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=json.loads(
            (ROOT/"reports/p1_pilot_16_source_digests_20261021.json").read_text())
        cls.new=json.loads(
            (ROOT/"reports/p1_delisted_8_source_digests_20261021.json").read_text())
        cls.one=ROOT/"manifests/baostock_pilot.txt"
        cls.two=ROOT/"manifests/baostock_delisted_8_pilot.txt"

    def baseline(self):
        return source_index(self.old,self.new,self.one,self.two)

    def synthetic(self):
        baseline,codes=self.baseline()
        baseline=copy.deepcopy(baseline)
        for code in codes:
            baseline[code]["sha256"]=source_sha(code)
            baseline[code]["rows"]=len(history(code))
        return baseline,codes

    def test_real_provenance_24_codes_order_not_claimed_official(self):
        baseline,codes=self.baseline()
        self.assertEqual(len(codes),24)
        self.assertEqual(len(baseline),24)
        self.assertEqual(len(set(codes)),24)
        self.assertEqual(codes[0],"sh.600000")
        self.assertEqual(codes[16],"sh.600421")
        self.assertTrue(all(len(baseline[code]["sha256"])==64
                            for code in codes))

    def test_byte_exact_synthetic_8_issuer_limited_batch(self):
        baseline,codes=self.synthetic()
        client=FakeClient()
        result=run(client,0,baseline,codes)
        self.assertEqual(result["status"],"EIGHT_SOURCE_BYTES_IDENTICAL_NOW_RESEARCH_ONLY")
        self.assertEqual(result["identical_source_count"],8)
        self.assertEqual(result["logical_issuer_queries"],8)
        self.assertEqual(len(client.queries),8)
        self.assertEqual(client.logouts,1)
        self.assertTrue(all(x["sha256_matches_frozen_original"] for x in result["source_entries"]))
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["candidate_universe"],[])
        self.assertEqual(result["orders"],[])
        self.assertFalse(result["original_raw_CSV_durably_archived"])
        self.assertFalse(result["provider_market_data_republication_license_verified"])
        self.assertFalse(result["all_24_history_recovered_in_this_run"])

    def test_single_vendor_history_revision_fails_batch(self):
        baseline,codes=self.synthetic()
        result=run(FakeClient(drift=True),0,baseline,codes)
        self.assertEqual(result["status"],"BLOCKED_INCOMPLETE_OR_REVISED")
        self.assertEqual(result["identical_source_count"],7)
        self.assertEqual(result["source_entries"][0]["status"],
                         "SOURCE_HISTORY_REVISION_OR_SCHEMA_DRIFT")
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_free_login_failed_no_fake_empty_history(self):
        baseline,codes=self.synthetic()
        client=FakeClient(login_failure=True)
        r=run(client,2,baseline,codes)
        self.assertEqual(r["identical_source_count"],0)
        self.assertEqual(r["logical_issuer_queries"],0)
        self.assertEqual(r["source_entries"],[])
        self.assertEqual(r["status"],"BLOCKED_INCOMPLETE_OR_REVISED")
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_batch_cap_and_stopping_unknown_index(self):
        baseline,codes=self.synthetic()
        for index in (-1,3,999):
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,"Unexpected"):
                run(FakeClient(),index,baseline,codes)
        with self.assertRaisesRegex(ValueError,"Unexpected"):
            run(FakeClient(),0,baseline,codes[:-1])

    def test_original_sha_drift_detected_before_query(self):
        old=copy.deepcopy(self.old)
        old["audit_report"]["trade_gate"]="READY"
        with self.assertRaisesRegex(ValueError,"promoted"):
            source_index(old,self.new,self.one,self.two)

    def test_wrong_issuer_and_schema_rejected(self):
        with self.assertRaisesRegex(ValueError,"identity"):
            compare_source("sh.600000",history("sz.000001"),
                           source_sha("sh.600000"),2)
        bad=history("sh.600000")
        bad[0][2]="11,00"
        with self.assertRaisesRegex(ValueError,"Malformed"):
            compare_source("sh.600000",bad,source_sha("sh.600000"),2)

    def test_delisted_last_vendor_day_is_not_last_tradable(self):
        result=compare_source("sh.600421",history("sh.600421"),
                              source_sha("sh.600421"),6)
        self.assertTrue(result["sha256_matches_frozen_original"])
        self.assertEqual(result["current_last_vendor_row"],"2026-06-25")
        self.assertEqual(result["current_last_trade_status_1"],"2026-06-22")


if __name__=="__main__":
    unittest.main()
