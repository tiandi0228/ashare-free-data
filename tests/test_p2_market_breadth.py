import unittest
from collector.p2_market_breadth import evaluate
class BreadthTests(unittest.TestCase):
    def source(self):
        codes=[f"sh.{600000+i:06d}" for i in range(3194)]
        return dict(asof="2026-11-25",universe=codes,returns=[dict(code=c,asof="2026-11-25",window_verified=True,return20_pct="2") for c in codes],trade_gate="BLOCKED",orders=[],executable_candidates=[],historical_PIT_verified=False)
    def test_strength(self):
        r=evaluate(self.source());self.assertEqual(r["research_state"],"BROAD_STRENGTH");self.assertFalse(r["macro_verified"]);self.assertEqual(r["orders"],[])
    def test_weakness(self):
        x=self.source()
        for r in x["returns"]:r["return20_pct"]="-2"
        self.assertEqual(evaluate(x)["research_state"],"BROAD_WEAKNESS")
    def test_coverage(self):
        x=self.source()
        for r in x["returns"][:100]:r["window_verified"]=False
        self.assertEqual(evaluate(x)["research_state"],"INSUFFICIENT_COVERAGE")
    def test_future(self):
        x=self.source();x["returns"][0]["asof"]="2026-11-26"
        with self.assertRaises(ValueError):evaluate(x)
    def test_duplicate(self):
        x=self.source();x["returns"][0]=x["returns"][1]
        with self.assertRaises(ValueError):evaluate(x)
