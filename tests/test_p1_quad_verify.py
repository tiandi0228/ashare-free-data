import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p1_quad_verify import verify
from collector.baostock_batch import FIELDS

def csv_data(code="sz.000001",date="2026-10-20",close="6.40",status="1"):
    row=[date,code,"6.40","6.50","6.30",close,"1000","6400","3",status]
    return (",".join(FIELDS)+"\n"+",".join(row)+"\n").encode()

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        shards=[];self.receipts=[]
        for index,code in enumerate(["sz.000001","sh.600001"]):
            raw=(code+"\n").encode();name=f"shard_{index:04d}.txt"
            (self.root/name).write_bytes(raw)
            data=csv_data(code)
            folder=self.root/f"batch{index}";folder.mkdir()
            self.write_csv(folder,code,data)
            sha=hashlib.sha256(raw).hexdigest()
            receipt={"status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "paid_api_calls":0,"manifest_sha256":sha,"issuer_count":1,
                     "query_attempts":1,"results":[{
                         "code":code,"status":"OBSERVED_UNVERIFIED",
                         "sha256":hashlib.sha256(data).hexdigest(),
                         "rows":1,"first":"2026-10-20","last":"2026-10-20",
                         "tradable_rows":1,"suspended_status_rows":0}]}
            (folder/"quality.json").write_text(json.dumps(receipt))
            shards.append({"index":index,"name":name,"sha256":sha,"count":1})
            self.receipts.append((index,folder))
        self.plan={"phase":"P1_FRESH_VENDOR_SHARD_PLAN","trade_gate":"BLOCKED",
                   "historical_PIT_verified":False,"shard_count":2,"shards":shards,
                   "source_sha256":"a"*64}
    def write_csv(self,folder,code,data):
        (folder/(code.replace(".","_")+".csv")).write_bytes(data)
    def replace_data(self,idx,data,**meta):
        index,folder=self.receipts[idx];code=["sz.000001","sh.600001"][idx]
        self.write_csv(folder,code,data)
        receipt=json.loads((folder/"quality.json").read_text())
        receipt["results"][0]["sha256"]=hashlib.sha256(data).hexdigest()
        receipt["results"][0].update(meta)
        (folder/"quality.json").write_text(json.dumps(receipt))
    def test_independent_ohlc_and_receipt_metadata(self):
        result=verify(self.plan,self.receipts,self.root)
        self.assertEqual(result["verified_issuers"],2)
        self.assertEqual(result["independently_checked_active_rows"],2)
        self.assertFalse(result["historical_PIT_verified"])
    def test_raw_sha_tamper_rejected(self):
        self.write_csv(self.receipts[1][1],"sh.600001",b"tampered")
        with self.assertRaises(ValueError):verify(self.plan,self.receipts,self.root)
    def test_invalid_ohlc_even_with_recalculated_sha_rejected(self):
        self.replace_data(0,csv_data(close="7.20"))
        with self.assertRaises(ValueError):verify(self.plan,self.receipts,self.root)
    def test_wrong_issuer_even_with_recalculated_sha_rejected(self):
        self.replace_data(0,csv_data(code="sz.000002"))
        with self.assertRaises(ValueError):verify(self.plan,self.receipts,self.root)
    def test_forged_receipt_row_count_rejected(self):
        self.replace_data(0,csv_data(),rows=999)
        with self.assertRaises(ValueError):verify(self.plan,self.receipts,self.root)
    def test_future_history_date_rejected(self):
        self.replace_data(0,csv_data(date="2026-10-21"),first="2026-10-21",last="2026-10-21")
        with self.assertRaises(ValueError):verify(self.plan,self.receipts,self.root)
    def test_suspended_status_consistent(self):
        self.replace_data(0,csv_data(status="0"),tradable_rows=0,suspended_status_rows=1)
        result=verify(self.plan,self.receipts,self.root)
        self.assertEqual(result["independently_checked_suspended_rows"],1)
    def test_duplicate_manifest_issuers_rejected(self):
        content=b"sz.000001\nsz.000001\n"
        (self.root/"shard_0000.txt").write_bytes(content)
        self.plan["shards"][0].update(sha256=hashlib.sha256(content).hexdigest(),count=2)
        r=json.loads((self.receipts[0][1]/"quality.json").read_text())
        r.update(manifest_sha256=hashlib.sha256(content).hexdigest(),issuer_count=2,query_attempts=2)
        r["results"]=r["results"]*2
        (self.receipts[0][1]/"quality.json").write_text(json.dumps(r))
        with self.assertRaises(ValueError):verify(self.plan,self.receipts,self.root)
if __name__=="__main__":unittest.main()
