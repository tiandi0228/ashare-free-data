import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p1_archive_audit import audit

def receipt_digest(receipt):
    return hashlib.sha256(json.dumps(receipt,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

class AuditTests(unittest.TestCase):
    def test_out_of_range_or_boolean_archive_indices_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); epoch=root/("a"*16)
            epoch.mkdir()
            plan={"source_sha256":"a"*64,"shards":[{"index":0,"sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"count":1}]}
            ledger={"source_sha256":"a"*64,"trade_gate":"BLOCKED","completed":[{"index":0}],"completed_issuers":1}
            for invalid in ([1],[-1],[True],["0"]):
                (epoch/"archive_status.json").write_text(json.dumps({
                    "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":invalid}))
                with self.assertRaises(ValueError):
                    audit(plan,ledger,root)

    def test_duplicate_issuer_within_archive_shard_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);epoch=root/("a"*16);part=epoch/"shard_0000"
            part.mkdir(parents=True)
            (epoch/"archive_status.json").write_text(json.dumps({
                "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[0]}))
            plan={"source_sha256":"a"*64,"shards":[{"index":0,"sha256":"b"*64,"count":2}]}
            ledger={"source_sha256":"a"*64,"trade_gate":"BLOCKED",
                    "completed":[{"index":0}],"completed_issuers":2}
            raw=b"date,close\\n2026-01-01,1\\n"
            (part/"sh_600000.csv").write_bytes(raw)
            row={"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}
            receipt={"manifest_sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"status":"OBSERVED_SUBSET_UNVERIFIED",
                     "trade_gate":"BLOCKED","results":[row,row]}
            (part/"quality.json").write_text(json.dumps(receipt))
            ledger["completed"][0]["receipt_sha256"]=receipt_digest(receipt)
            with self.assertRaisesRegex(ValueError,"duplicate"):
                audit(plan,ledger,root)

    def test_cross_shard_duplicate_issuer_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);epoch=root/("a"*16)
            epoch.mkdir()
            (epoch/"archive_status.json").write_text(json.dumps({
                "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[0,1]}))
            plan={"source_sha256":"a"*64,"shards":[
                {"index":0,"sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"count":1},
                {"index":1,"sha256":"c"*64,"count":1}]}
            raw=b"date,close\\n2026-01-01,1\\n"
            ledger={"source_sha256":"a"*64,"trade_gate":"BLOCKED",
                    "completed":[],"completed_issuers":2}
            for index,sha in [(0,"b"*64),(1,"c"*64)]:
                part=epoch/f"shard_{index:04d}";part.mkdir()
                (part/"sh_600000.csv").write_bytes(raw)
                receipt={"manifest_sha256":sha,"status":"OBSERVED_SUBSET_UNVERIFIED",
                         "trade_gate":"BLOCKED","results":[{
                             "code":"sh.600000","status":"OBSERVED_UNVERIFIED",
                             "sha256":hashlib.sha256(raw).hexdigest()}]}
                (part/"quality.json").write_text(json.dumps(receipt))
                ledger["completed"].append({"index":index,
                    "receipt_sha256":receipt_digest(receipt)})
            with self.assertRaisesRegex(ValueError,"across shards"):
                audit(plan,ledger,root)

    def test_archive_membership_hash_must_match_original_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);epoch=root/("a"*16);part=epoch/"shard_0000"
            part.mkdir(parents=True)
            (epoch/"archive_status.json").write_text(json.dumps({
                "source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[0]}))
            raw=b"date,close\\n2026-01-01,1\\n"
            (part/"sh_600000.csv").write_bytes(raw)
            receipt={"manifest_sha256":"b"*64,"status":"OBSERVED_SUBSET_UNVERIFIED",
                     "trade_gate":"BLOCKED","results":[{"code":"sh.600000",
                     "status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}]}
            (part/"quality.json").write_text(json.dumps(receipt))
            plan={"source_sha256":"a"*64,"shards":[{"index":0,"sha256":"b"*64,"count":1}]}
            ledger={"source_sha256":"a"*64,"trade_gate":"BLOCKED","completed":[{
                "index":0,"receipt_sha256":receipt_digest(receipt)}],"completed_issuers":1}
            with self.assertRaisesRegex(ValueError,"membership"):
                audit(plan,ledger,root)

    def test_legacy_without_receipt_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);epoch=root/("a"*16);part=epoch/"shard_0000"
            part.mkdir(parents=True)
            (epoch/"archive_status.json").write_text(json.dumps({"source_sha256":"a"*64,"trade_gate":"BLOCKED","archived_shards":[0]}))
            plan={"source_sha256":"a"*64,"shards":[{"index":0,"sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"count":1}]}
            ledger={"source_sha256":"a"*64,"trade_gate":"BLOCKED","completed":[{"index":0}],"completed_issuers":1}
            result=audit(plan,ledger,root)
            self.assertEqual(result["archived_issuers"],0)
            self.assertEqual(result["source_sha256"],"a"*64)
            self.assertEqual(result["legacy_shards_without_receipts"],[0])
            self.assertEqual(result["archive_repair_queue"],[0])
            self.assertEqual(result["repair_shard_count"],1)
            raw=b"date,close\n2026-01-01,1\n"
            (part/"sh_600000.csv").write_bytes(raw)
            receipt={"manifest_sha256":hashlib.sha256(b"sh.600000\n").hexdigest(),"status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED","results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED","sha256":hashlib.sha256(raw).hexdigest()}]}
            (part/"quality.json").write_text(json.dumps(receipt))
            ledger["completed"][0]["receipt_sha256"]=receipt_digest(receipt)
            self.assertEqual(audit(plan,ledger,root)["archived_issuers"],1)
            invalid=dict(receipt)
            invalid["results"]=[{**receipt["results"][0],"status":"ERROR"}]
            (part/"quality.json").write_text(json.dumps(invalid))
            ledger["completed"][0]["receipt_sha256"]=receipt_digest(invalid)
            with self.assertRaisesRegex(ValueError,"issuer result status"):
                audit(plan,ledger,root)
            (part/"quality.json").write_text(json.dumps(receipt))
            ledger["completed"][0]["receipt_sha256"]=receipt_digest(receipt)
            ledger["completed"][0]["receipt_sha256"]="0"*64
            with self.assertRaisesRegex(ValueError,"immutable ledger"):
                audit(plan,ledger,root)
            ledger["completed"][0]["receipt_sha256"]=receipt_digest(receipt)
            self.assertEqual(audit(plan,ledger,root)["archive_repair_queue"],[])
            (part/"sh_600000.csv").write_text("corrupt")
            with self.assertRaises(ValueError):audit(plan,ledger,root)
if __name__=="__main__":unittest.main()
