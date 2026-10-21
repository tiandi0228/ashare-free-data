"""Vendor byte-identical re-fetch is possible to TEST, never guaranteed."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from collector.baostock_batch import FIELDS
from collector.reacquire_source_digest import originals, reacquire

ROOT=Path(__file__).resolve().parents[1]/"reports"


def row(day,code,status="1",price="10.00"):
    return [day,code,price,price,price,price,"100","1000","3",status]


def example(code):
    if code=="sh.600421":
        dates=[("2026-05-26","0"),("2026-06-01","1"),
               ("2026-06-22","1"),("2026-06-23","0"),
               ("2026-06-24","0"),("2026-06-25","0")]
    else:
        dates=[("2026-06-22","1"),("2026-06-23","1")]
    return [row(d,code,s) for d,s in dates]


def raw(rows):
    return (",".join(FIELDS)+"\n"+
            "".join(",".join(row)+"\n" for row in rows)).encode()


class Result:
    error_code="0"
    fields=FIELDS
    def __init__(self,rows):
        self.rows=rows; self.index=0
    def next(self):
        if self.index>=len(self.rows):return False
        self.index+=1;return True
    def get_row_data(self):
        return self.rows[self.index-1]


class FakeProvider:
    def __init__(self,drift=False,login_fail=False):
        self.calls=[];self.logouts=0;self.drift=drift;self.login_fail=login_fail
    def login(self):
        return type("L",(),{"error_code":"101" if self.login_fail else "0"})()
    def logout(self):
        self.logouts+=1
    def query_history_k_data_plus(self,code,**kwargs):
        self.calls.append((code,kwargs))
        r=example(code)
        if self.drift and code=="sh.600421":
            r[1][2]="12.00";r[1][3]="12.00";r[1][4]="12.00";r[1][5]="12.00"
        return Result(r)


class ReacquireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=json.loads((ROOT/"p1_pilot_16_source_digests_20261021.json").read_text())
        cls.new=json.loads((ROOT/"p1_delisted_8_source_digests_20261021.json").read_text())

    def fixture(self):
        old,new=copy.deepcopy(self.old),copy.deepcopy(self.new)
        for a,code,k in (
            (new["replay_report"]["source_receipts"],"sh.600421","original_csv_sha256"),
            (old["audit_report"]["issuers"],"sh.600000","source_sha256"),
        ):
            item=next(x for x in a if x["code"]==code)
            item[k]=hashlib.sha256(raw(example(code))).hexdigest()
            item["source_rows"]=len(example(code))
        return old,new

    def test_identical_now_never_archival_certification(self):
        old,new=self.fixture()
        bs=FakeProvider()
        r=reacquire(bs,old,new)
        self.assertEqual(r["status"],"TWO_SOURCES_REACQUIRED_IDENTICAL_NOW_NO_DURABLE_STORAGE")
        self.assertEqual(r["issuer_queries"],2)
        self.assertEqual(len(bs.calls),2)
        self.assertEqual(bs.logouts,1)
        self.assertTrue(all(x["same_SHA256_and_row_count"] for x in r["source_reports"]))
        self.assertFalse(r["source_raw_bytes_durably_archived"])
        self.assertFalse(r["source_raw_csv_republished"])
        self.assertFalse(r["publication_instant_authenticated"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])

    def test_historical_source_revision_rejected_without_relabel(self):
        old,new=self.fixture()
        bs=FakeProvider(drift=True)
        r=reacquire(bs,old,new)
        self.assertEqual(r["status"],"BLOCKED_VENDOR_HISTORICAL_REVISION_DETECTED")
        self.assertEqual(r["source_reports"][0]["status"],"SOURCE_HISTORY_VERSION_DRIFT")
        self.assertFalse(r["source_reports"][0]["same_SHA256_and_row_count"])
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_login_blocked_cannot_invent_recovery(self):
        old,new=self.fixture()
        bs=FakeProvider(login_fail=True)
        r=reacquire(bs,old,new)
        self.assertEqual(r["status"],"BLOCKED_PARTIAL")
        self.assertEqual(r["issuer_queries"],0)
        self.assertEqual(r["source_reports"],[])
        self.assertEqual(r["paid_api_calls"],0)

    def test_original_capture_ids_not_invented(self):
        old,new=self.fixture()
        old["capture_run_ids"]=[0,0]
        with self.assertRaisesRegex(ValueError,"not eligible"):
            originals(old,new)

    def test_derived_sha_is_not_original_artifact_bytes(self):
        old,new=self.fixture()
        b=FakeProvider()
        r=reacquire(b,old,new)
        self.assertTrue(r["provider_historical_version_can_change"])
        self.assertFalse(r["all_market_replay_ready"])
        self.assertFalse(r["official_exchange_historical_risk_verified"])
        self.assertTrue(all("observed_SHA256" in e for e in r["source_reports"]))
        self.assertTrue(all("raw" not in e for e in r["source_reports"]))

if __name__=="__main__":
    unittest.main()
