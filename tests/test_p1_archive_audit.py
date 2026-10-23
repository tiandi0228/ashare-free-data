import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p1_archive_audit import audit

class AuditTests(unittest.TestCase):
    def test_legacy_without_receipt_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);epoch=root/("a"*16);part=epoch/"shard_0000"
            part.mkdir(parents=True)
            (epoch/"archive_status.json").write_text(json.dumps({"source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[0]}))
            plan={"source_sha256":"a"*64,"shards":[{"index":0,"sha256":"b"*64,"count":1}]}
            ledger={"source_sha256":"a"*64,"trade_gate":"BLOCKED","completed":[{"index":0}],"completed_issuers":1}
            result=audit(plan,ledger,root)
            self.assertEqual(result["archived_issuers"],0)
            self.assertEqual(result["legacy_shards_without_receipts"],[0])
            raw=b"date,close\n2026-01-01,1\n"
            (part/"sh_600000.csv").write_bytes(raw)
            (part/"quality.json").write_text(json.dumps({"manifest_sha256":"b"*64,"status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED","results":[{"code":"sh.600000","sha256":hashlib.sha256(raw).hexdigest()}]}))
            self.assertEqual(audit(plan,ledger,root)["archived_issuers"],1)
            (part/"sh_600000.csv").write_text("corrupt")
            with self.assertRaises(ValueError):audit(plan,ledger,root)
if __name__=="__main__":unittest.main()
