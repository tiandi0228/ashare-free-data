import json,unittest
from tests.test_p2_refresh_batch_replay import ReplayTests
from collector.p2_refresh_aggregate import aggregate

class AggregateTests(unittest.TestCase):
    def setUp(self):
        fixture=ReplayTests("test_valid")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.m,self.r,self.root,self.ext=fixture.m,fixture.r,fixture.root,fixture.ext
        (self.ext/"receipt.json").write_text(json.dumps(self.r))
    def test_empty_not_coverage(self):
        r=aggregate(self.m,self.root,[])
        self.assertEqual(r["accepted_issuers"],0)
        self.assertFalse(r["full_universe_observed"])
    def test_independent_acceptance(self):
        r=aggregate(self.m,self.root,[self.ext])
        self.assertEqual(r["accepted_batches"],1)
        self.assertEqual(r["research_feature_issuers"],1)
        self.assertTrue(r["full_universe_observed"])
        self.assertFalse(r["historical_PIT_verified"])
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):aggregate(self.m,self.root,[self.ext,self.ext])
    def test_tampered_package_rejected(self):
        (self.ext/"sh_600150.csv").write_bytes(b"tampered")
        with self.assertRaises(ValueError):aggregate(self.m,self.root,[self.ext])
