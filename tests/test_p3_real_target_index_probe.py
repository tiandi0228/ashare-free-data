import unittest
from collector.p3_real_target_index_probe import run
class ProbeTests(unittest.TestCase):
    def sample(self):
        return {"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE","trade_gate":"BLOCKED",
                "targets":[{"issuer":"sz.000001"},{"issuer":"sh.600000"}]}
    def test_distinct_issuer_lookup_and_no_pit(self):
        r=run(self.sample(),lambda x:[])
        self.assertEqual(r["attempted"],2)
        self.assertEqual(r["results"][0]["status"],"NO_INDEX_MATCH_NOT_NO_RISK")
        self.assertFalse(r["historical_PIT_verified"])
    def test_unavailable_is_not_clearance(self):
        def bad(x):raise TimeoutError("unavailable")
        self.assertEqual(run(self.sample(),bad)["results"][0]["status"],"INDEX_UNAVAILABLE_NOT_NO_RISK")
if __name__=="__main__":unittest.main()
