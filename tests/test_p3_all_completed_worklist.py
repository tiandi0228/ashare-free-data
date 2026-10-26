import csv,hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p3_all_completed_worklist import build
from collector.baostock_batch import FIELDS

def source_row(code,day,active=True):
    vals=[day,code,"6.40","6.50","6.30","6.40","1000","6400","3","1"] if active else [day,code,"","","","","","","3","0"]
    return ",".join(vals)
class FullQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.sha="a"*64;epoch=self.root/self.sha[:16];epoch.mkdir()
        shards=[];done=[]
        for n,code in enumerate(("sz.000001","sh.600001")):
            manifest=hashlib.sha256((code+"\n").encode()).hexdigest()
            part=epoch/f"shard_{n:04d}";part.mkdir()
            contents=",".join(FIELDS)+"\n"+source_row(code,"2026-10-19",active=n==1)+"\n"+source_row(code,"2026-10-20")+"\n"
            raw=contents.encode()
            (part/(code.replace(".","_")+".csv")).write_bytes(raw)
            receipt={"phase":"BAOSTOCK_FREE_BOUNDED_BATCH","status":"OBSERVED_SUBSET_UNVERIFIED",
                     "manifest_sha256":manifest,"issuer_count":1,
                     "historical_point_in_time_universe_verified":False,
                     "trade_gate":"BLOCKED","orders":[],"results":[{
                         "code":code,"status":"OBSERVED_UNVERIFIED",
                         "sha256":hashlib.sha256(raw).hexdigest(),
                         "rows":2,"tradable_rows":2 if n else 1,
                         "suspended_status_rows":0 if n else 1}]}
            (part/"quality.json").write_text(json.dumps(receipt))
            digest=hashlib.sha256(json.dumps(receipt,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            shards.append({"index":n,"sha256":manifest,"count":1})
            done.append({"index":n,"manifest_sha256":manifest,
                         "issuer_count":1,"receipt_sha256":digest})
        (epoch/"archive_status.json").write_text(json.dumps({
            "source_sha256":self.sha,"trade_gate":"BLOCKED","archived_shards":[0,1]}))
        self.plan={"phase":"P1_FRESH_VENDOR_SHARD_PLAN","source_sha256":self.sha,
                   "trade_gate":"BLOCKED","historical_PIT_verified":False,
                   "shard_count":2,"shards":shards}
        self.ledger={"source_sha256":self.sha,"trade_gate":"BLOCKED",
                     "historical_PIT_verified":False,"shard_count":2,"completed":done,
                     "completed_shards":2,"completed_issuers":2}
    def test_entire_completed_checkpoint_not_latest_only(self):
        q=build(self.root,self.plan,self.ledger)
        self.assertEqual(q["completed_issuers_replayed"],2)
        self.assertEqual(q["required_official_evidence_cells"],16)
        self.assertTrue(q["vendor_suspended_context_included"])
        self.assertEqual(q["issuers_with_vendor_nontrading_history"],1)
        risk=[t for t in q["official_evidence_tasks"] if t["issuer"]=="sz.000001" and t["decision_day"]=="2026-10-19"]
        self.assertEqual(len(risk),4)
        self.assertTrue(all(t["vendor_tradestatus_observed"]=="0" for t in risk))
        self.assertTrue(all(t["historical_asof_verified"] is False for t in risk))
        self.assertEqual({r["issuer"] for r in q["official_evidence_tasks"]},{"sz.000001","sh.600001"})
        self.assertEqual(q["independently_verified_official_PIT_cells"],0)
        self.assertEqual(q["frozen_vendor_query_end"],"2026-10-20")
    def test_last_vendor_active_to_halt_transition_retained(self):
        part=self.root/self.sha[:16]/"shard_0001"
        code="sh.600001";path=part/"sh_600001.csv"
        content=",".join(FIELDS)+"\n"+source_row(code,"2026-10-16")+"\n"+source_row(code,"2026-10-19",active=False)+"\n"+source_row(code,"2026-10-20",active=False)+"\n"
        data=content.encode()
        path.write_bytes(data)
        receipt=json.loads((part/"quality.json").read_text())
        receipt["results"][0].update(sha256=hashlib.sha256(data).hexdigest(),
                                    rows=3,tradable_rows=1,suspended_status_rows=2)
        (part/"quality.json").write_text(json.dumps(receipt))
        self.ledger["completed"][1]["receipt_sha256"]=hashlib.sha256(
            json.dumps(receipt,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        result=build(self.root,self.plan,self.ledger)
        relevant=[x for x in result["official_evidence_tasks"]
                  if x["issuer"]==code and x["status_kind"]=="halt"]
        transitions=[x["decision_day"] for x in relevant
                     if x["vendor_possible_halt_transition_observed"]]
        self.assertEqual(transitions,["2026-10-19"])
        self.assertTrue(all(x["historical_asof_verified"] is False for x in relevant))
    def test_changed_source_sha_rejected(self):
        with self.assertRaises(ValueError):
            build(self.root,{**self.plan,"source_sha256":"b"*64},self.ledger)
    def test_missing_archive_completed_shard_rejected(self):
        p=self.root/self.sha[:16]/"archive_status.json"
        x=json.loads(p.read_text());x["archived_shards"]=[0];p.write_text(json.dumps(x))
        with self.assertRaises(ValueError):build(self.root,self.plan,self.ledger)
    def test_original_sha_tampering_rejected(self):
        p=self.root/self.sha[:16]/"shard_0000"/"quality.json"
        x=json.loads(p.read_text());x["results"][0]["rows"]=999;p.write_text(json.dumps(x))
        with self.assertRaises(ValueError):build(self.root,self.plan,self.ledger)
    def test_forged_csv_with_stale_receipt_rejected(self):
        p=self.root/self.sha[:16]/"shard_0000"/"sz_000001.csv"
        p.write_bytes(p.read_bytes().replace(b"6.40",b"9.40",1))
        with self.assertRaises(ValueError):build(self.root,self.plan,self.ledger)
if __name__=="__main__":unittest.main()
