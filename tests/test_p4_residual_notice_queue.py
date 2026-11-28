import unittest
from collector.p4_residual_notice_queue import build
class ResidualTests(unittest.TestCase):
    def setUp(self):
        base=dict(asof="2026-11-25",trade_gate="BLOCKED",orders=[],executable_candidates=[],official_limit_certified=0,historical_PIT_verified=False)
        self.q=dict(base,source_artifact_sha256="a"*64,tasks=[dict(code="sh.600%03d"%i,day="2026-11-03",priority="P1_DIRECTIONAL",extension_sha256="b"*64) for i in range(23)])
        self.l=dict(base,priority_targets=23,original_notice_leads=5,records=[dict(code=t["code"],day=t["day"],source_sha256="c"*64,official_limit_verified=False,first_publication_verified=False,fill_verified=False) for t in self.q["tasks"][:5]])
    def test_remaining(self):
        r=build(self.q,self.l)
        self.assertEqual(r["remaining_notice_tasks"],18)
        self.assertEqual(r["tasks"][0]["code"],"sh.600005")
        self.assertEqual(r["official_limit_certified"],0)
    def test_duplicate(self):
        self.l["records"].append(self.l["records"][0])
        with self.assertRaises(ValueError):build(self.q,self.l)
    def test_unsafe(self):
        self.l["records"][0]["fill_verified"]=True
        with self.assertRaises(ValueError):build(self.q,self.l)
    def test_wrong_epoch(self):
        self.l["asof"]="2026-11-24"
        with self.assertRaises(ValueError):build(self.q,self.l)
