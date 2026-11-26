import hashlib,tempfile,unittest
from pathlib import Path
from collector.p2_refresh_checkpoint import digest
from collector.p2_refresh_batch_replay import verify
from collector.p2_gap_extension_replay import inspect
from collector.p2_independent_bars import FIELDS
from collector.p4_curated_session_exit import sessions_between

SAFE=dict(trade_gate="BLOCKED",orders=[],executable_candidates=[],historical_PIT_verified=False)
def raw(days):
    return (",".join(FIELDS)+"\n"+"".join(f"{d},sh.600150,10,10,10,10,100,1000,3,1\n" for d in days)).encode()
class ReplayTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)/("a"*16);self.ext=Path(t.name)/"extension"
        shard=self.root/"shard_0000";shard.mkdir(parents=True);self.ext.mkdir()
        a=raw(["2026-10-20"]);b=raw(sessions_between("2026-10-21","2026-11-25"))
        (shard/"sh_600150.csv").write_bytes(a);(self.ext/"sh_600150.csv").write_bytes(b)
        src=dict(code="sh.600150",source_shard="shard_0000",original_csv_sha256=hashlib.sha256(a).hexdigest())
        rows=[src];sha=digest(rows)
        self.m=dict(SAFE,epoch="a"*64,batch_size=8,batch_count=1,issuer_count=1,batches=[dict(index=0,manifest_sha256=sha,issuers=rows)])
        self.r=dict(SAFE,epoch="a"*64,batch_index=0,manifest_sha256=sha,asof="2026-11-25",results=[dict(code=src["code"],original_csv_sha256=src["original_csv_sha256"],extension_sha256=hashlib.sha256(b).hexdigest(),status="FEATURE_WINDOW_OBSERVED",research_features=inspect(a,b,src["code"])["research_features"])])
    def test_valid(self):
        r=verify(self.m,self.r,self.root,self.ext)
        self.assertTrue(r["original_bytes_replayed"]);self.assertEqual(r["research_feature_issuers"],1)
    def test_tamper(self):
        (self.ext/"sh_600150.csv").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):verify(self.m,self.r,self.root,self.ext)
    def test_false_claim(self):
        self.r["results"][0]["research_features"]["ma20_close_cny"]="99"
        with self.assertRaisesRegex(ValueError,"claimed features"):verify(self.m,self.r,self.root,self.ext)
