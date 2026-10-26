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
        self.assertEqual({r["issuer"] for r in q["official_evidence_tasks"]},{"sz.000001","sh.600001"})
        self.assertEqual(q["independently_verified_official_PIT_cells"],0)
        self.assertEqual(q["frozen_vendor_query_end"],"2026-10-20")
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
