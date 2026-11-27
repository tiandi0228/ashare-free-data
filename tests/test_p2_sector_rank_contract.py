import unittest
from collector.p2_sector_rank_contract import rank
class SectorTests(unittest.TestCase):
    def setUp(self):
        self.codes=["sh.600001","sh.600002","sh.600003","sh.600004"]
        self.day="2026-11-25"
        self.m=[dict(code=c,sector="A",effective_from="2026-01-01",effective_to=None,published_at="2026-01-01T09:00:00+08:00",publication_verified=True,source_sha256="a"*64) for c in self.codes]
        self.r=[dict(code=c,asof=self.day,window_verified=True,return20_pct=i) for i,c in enumerate(self.codes)]
    def test_top3(self):
        r=rank(self.day,self.codes,self.m,self.r)
        self.assertEqual([x["code"] for x in r["research_top3"]],self.codes[::-1][:3])
        self.assertEqual(r["orders"],[]);self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_future_publication(self):
        self.m[0]["published_at"]="2026-11-25T15:01:00+08:00"
        r=rank(self.day,self.codes,self.m,self.r)
        self.assertEqual(r["membership_covered"],3);self.assertEqual(r["research_top3"],[])
    def test_expired_membership(self):
        self.m[0]["effective_to"]=self.day
        self.assertEqual(rank(self.day,self.codes,self.m,self.r)["joint_covered"],3)
    def test_overlap(self):
        with self.assertRaises(ValueError):rank(self.day,self.codes,self.m+[dict(self.m[0])],self.r)
    def test_unknown_return(self):
        self.r[0]["window_verified"]=False
        self.assertEqual(rank(self.day,self.codes,self.m,self.r)["research_top3"],[])
    def test_no_sources(self):
        r=rank(self.day,self.codes,[],[])
        self.assertEqual(r["status"],"BLOCKED_INCOMPLETE_RESEARCH_INPUT")
        self.assertEqual(r["executable_candidates"],[])
