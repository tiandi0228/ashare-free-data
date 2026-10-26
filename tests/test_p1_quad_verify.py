import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p1_quad_verify import verify
class ReceiptTests(unittest.TestCase):
    def test_independent_sha_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);shards=[];receipts=[]
            for index,code in enumerate(["sz.000001","sh.600001"]):
                raw=(code+"\n").encode();name=f"shard_{index:04d}.txt"
                (root/name).write_bytes(raw)
                csv=b"date,code,close\n2026-10-20,"+code.encode()+b",6.40\n"
                folder=root/f"batch{index}";folder.mkdir()
                (folder/(code.replace(".","_")+".csv")).write_bytes(csv)
                sha=hashlib.sha256(raw).hexdigest()
                (folder/"quality.json").write_text(json.dumps({
                    "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                    "paid_api_calls":0,"manifest_sha256":sha,"issuer_count":1,
                    "query_attempts":1,"results":[{"code":code,"status":"OBSERVED_UNVERIFIED",
                    "sha256":hashlib.sha256(csv).hexdigest()}]}))
                shards.append({"index":index,"name":name,"sha256":sha,"count":1})
                receipts.append((index,folder))
            plan={"shard_count":2,"shards":shards,"source_sha256":"a"*64}
            self.assertEqual(verify(plan,receipts,root)["verified_issuers"],2)
            (root/"batch1"/"sh_600001.csv").write_text("tampered")
            with self.assertRaises(ValueError):verify(plan,receipts,root)
if __name__=="__main__":unittest.main()
