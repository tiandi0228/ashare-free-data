import unittest
from copy import deepcopy
from collector.p2_refresh_checkpoint import digest,reconcile

SAFE=dict(trade_gate="BLOCKED",orders=[],executable_candidates=[],historical_PIT_verified=False)
ROWS=[dict(code="sh.600150",original_csv_sha256="a"*64)]
MAN=dict(SAFE,epoch="b"*64,batch_size=8,batch_count=1,issuer_count=1,batches=[dict(index=0,issuers=ROWS,manifest_sha256=digest(ROWS))])
REC=dict(SAFE,epoch=MAN["epoch"],batch_index=0,manifest_sha256=digest(ROWS),asof="2026-11-25",results=[dict(**ROWS[0],status="FEATURE_WINDOW_OBSERVED",extension_sha256="c"*64)])

class CheckpointTests(unittest.TestCase):
    def test_empty(self):
        r=reconcile(MAN,[])
        self.assertEqual(r["pending_batch_indices"],[0])
        self.assertEqual(r["coverage_batches_accepted"],0)
    def test_structural_not_coverage(self):
        r=reconcile(MAN,[REC])
        self.assertEqual(r["structurally_complete_batches"],1)
        self.assertEqual(r["coverage_batches_accepted"],0)
    def test_duplicate(self):
        with self.assertRaises(ValueError):reconcile(MAN,[REC,REC])
    def test_bad_binding(self):
        for field,value in [("asof","2026-11-24"),("epoch","d"*64),("manifest_sha256","e"*64),("trade_gate","OPEN"),("results",[])]:
            r=deepcopy(REC);r[field]=value
            with self.assertRaises(ValueError):reconcile(MAN,[r])
