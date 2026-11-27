import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p2_full_refresh_manifest import build
class ManifestTests(unittest.TestCase):
    def test_reconcile_and_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/("a"*16);shard=root/"shard_0000";shard.mkdir(parents=True)
            p=shard/"sh_600150.csv";p.write_bytes(b"original")
            item=dict(code="sh.600150",status="OBSERVED_UNVERIFIED",sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            (shard/"quality.json").write_text(json.dumps(dict(status="OBSERVED_SUBSET_UNVERIFIED",trade_gate="BLOCKED",historical_point_in_time_universe_verified=False,results=[item])))
            cov=dict(source_epoch_sha256="a"*64,trade_gate="BLOCKED",full_archive_evidence_accounted=True,historical_PIT_verified=False,observed_feature_or_gap_issuers=1,gap_issuer_codes=[])
            r=build(cov,root);self.assertEqual(r["issuer_count"],1);self.assertEqual(r["provider_calls"],0)
            p.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError,"hash mismatch"):build(cov,root)
