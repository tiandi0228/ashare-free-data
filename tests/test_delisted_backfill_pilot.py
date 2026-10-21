"""One-off 8 issuer bounded historical pilot including a delisted original."""
from pathlib import Path
import json
import tempfile
import unittest
from collector.baostock_batch import manifest, run, FIELDS

ROOT=Path(__file__).resolve().parents[1]
NEW=ROOT/"manifests/baostock_delisted_8_pilot.txt"
OLD=ROOT/"manifests/baostock_pilot.txt"

class FakeResult:
    error_code="0"
    fields=FIELDS
    def __init__(self,code,empty=False):
        self.code=code;self.empty=empty;self.n=0
    def next(self):
        self.n+=1
        return self.n==1 and not self.empty
    def get_row_data(self):
        return ["2026-05-20",self.code,"1","1","1","1","100","100","3","1"]

class FakeBaostock:
    def __init__(self,delisted_empty=False):
        self.delisted_empty=delisted_empty;self.queries=[];self.logouts=0
    def login(self):
        return type("Login",(),{"error_code":"0"})()
    def logout(self):self.logouts+=1
    def query_history_k_data_plus(self,code,**kwargs):
        self.queries.append(code)
        return FakeResult(code,empty=code=="sh.600421" and self.delisted_empty)

class DelistedBatchTests(unittest.TestCase):
    def test_frozen_8_distinct_no_overlap_with_16(self):
        codes,_=manifest(NEW)
        old,_=manifest(OLD)
        self.assertEqual(len(codes),8)
        self.assertEqual(len(set(codes)),8)
        self.assertEqual(set(codes).intersection(old),set())
        self.assertEqual(codes[0],"sh.600421")
    def test_success_is_only_research_source_not_pit(self):
        with tempfile.TemporaryDirectory() as d:
            client=FakeBaostock()
            self.assertEqual(run(NEW,0,d,client),0)
            r=json.loads((Path(d)/"quality.json").read_text())
            self.assertEqual(client.queries,manifest(NEW)[0])
            self.assertEqual(client.logouts,1)
            self.assertEqual(r["query_attempts"],8)
            self.assertEqual(r["issuer_count"],8)
            self.assertFalse(r["full_market_history_verified"])
            self.assertFalse(r["historical_point_in_time_universe_verified"])
            self.assertEqual(r["trade_gate"],"BLOCKED")
            self.assertEqual(r["orders"],[])
    def test_missing_delisted_history_must_fail_even_if_7_others_succeed(self):
        with tempfile.TemporaryDirectory() as d:
            client=FakeBaostock(delisted_empty=True)
            self.assertEqual(run(NEW,0,d,client),2)
            r=json.loads((Path(d)/"quality.json").read_text())
            self.assertEqual(r["status"],"BLOCKED_PARTIAL")
            self.assertEqual(len(r["results"]),8)
            self.assertEqual(r["results"][0]["status"],"ERROR")
            self.assertEqual(sum(x["status"]=="OBSERVED_UNVERIFIED" for x in r["results"]),7)
            self.assertEqual(r["orders"],[])
            self.assertEqual(r["trade_gate"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
