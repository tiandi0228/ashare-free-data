import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p1_csv_archive import collect

class CSVArchiveTests(unittest.TestCase):
    def test_verified_csv_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\n2026-01-01,1.2\n"
            (path/"sh_600000.csv").write_bytes(raw)
            plan={"shards":[{"sha256":"a"*64,"count":1}]}
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,"status":"OBSERVED_SUBSET_UNVERIFIED",
                     "trade_gate":"BLOCKED","results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            result=collect(plan,[(0,path)])
            self.assertEqual(len(result),1)
            (path/"sh_600000.csv").write_text("tampered")
            with self.assertRaises(ValueError):collect(plan,[(0,path)])
    def test_duplicate_issuer_rejected_before_archive_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\n2026-01-01,1.2\n"
            (path/"sh_600000.csv").write_bytes(raw)
            item={"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}
            plan={"shards":[{"sha256":"a"*64,"count":2}]}
            receipt={"manifest_sha256":"a"*64,"issuer_count":2,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[item,item]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"duplicate issuer"):
                collect(plan,[(0,path)])

    def test_duplicate_shard_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\n2026-01-01,1.2\n"
            (path/"sh_600000.csv").write_bytes(raw)
            plan={"shards":[{"sha256":"a"*64,"count":1}]}
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"duplicate archive shard"):
                collect(plan,[(0,path),(0,path)])

    def test_failed_issuer_result_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\\n2026-01-01,1.2\\n"
            (path/"sh_600000.csv").write_bytes(raw)
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sh.600000","status":"ERROR",
                                 "sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"result status"):
                collect({"shards":[{"sha256":"a"*64,"count":1}]},[(0,path)])

    def test_missing_issuer_status_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            raw=b"date,close\\n2026-01-01,1.2\\n"
            (path/"sh_600000.csv").write_bytes(raw)
            plan={"shards":[{"sha256":"a"*64,"count":1}]}
            receipt={"manifest_sha256":"a"*64,"issuer_count":1,
                     "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                     "results":[{"code":"sh.600000",
                                 "sha256":hashlib.sha256(raw).hexdigest()}]}
            (path/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,"result status"):
                collect(plan,[(0,path)])

    def test_blocked_gate_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            plan={"shards":[{"sha256":"a"*64,"count":0}]}
            (path/"quality.json").write_text(json.dumps({"manifest_sha256":"a"*64,"issuer_count":0,"status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"OPEN","results":[]}))
            with self.assertRaises(ValueError):collect(plan,[(0,path)])
if __name__=="__main__":unittest.main()
