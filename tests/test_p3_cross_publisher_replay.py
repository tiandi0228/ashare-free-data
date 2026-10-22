"""Checks real committed official and issuer original hash replay receipts."""
import copy,json,unittest
from pathlib import Path
from collector.p3_cross_publisher_replay import audit
R=Path(__file__).resolve().parents[1]/"reports"
N=["p3_600421_two_pdf_event_chain_20261021.json","p3_sse_two_official_original_sha_observed_20261022.json","p3_cninfo_two_pdf_independent_sha_recapture_20261022.json","p3_sse_independent_two_originals_verified_20261022.json"]
class PublisherReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q=[json.loads((R/n).read_text()) for n in N]
    def test_four_real_source_receipts(self):
        r=audit(*self.q)
        self.assertEqual(r["independently_replayed_originals"],4)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["historical_publication_instant_verified"])
        self.assertTrue(r["evidence_layers"]["official_SSE_delist_notice_observed"])
        self.assertFalse(r["evidence_layers"]["historical_point_in_time_membership_proven"])
        self.assertEqual(len(r["missing_acceptance_requirements"]),5)
        self.assertFalse(r["historical_risk_coverage_complete"])
    def test_changed_source_digest_rejected(self):
        q=copy.deepcopy(self.q);q[3]["results"][0]["sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"mismatch"):audit(*q)
    def test_replay_wrong_url_rejected(self):
        q=copy.deepcopy(self.q);q[3]["results"][0]["url"]="https://example.invalid/"
        with self.assertRaisesRegex(ValueError,"URL or size"):audit(*q)
    def test_replay_wrong_length_rejected(self):
        q=copy.deepcopy(self.q);q[2]["sources"][0]["bytes"]=1
        with self.assertRaisesRegex(ValueError,"URL or size"):audit(*q)
    def test_not_independent_run_rejected(self):
        q=copy.deepcopy(self.q);q[3]["first_run_id"]=q[3]["second_run_id"]
        with self.assertRaisesRegex(ValueError,"capture identity"):audit(*q)
    def test_forged_timestamp_rejected(self):
        q=copy.deepcopy(self.q);q[2]["historical_asof_publication_instant_verified"]=True
        with self.assertRaisesRegex(ValueError,"PIT proof"):audit(*q)
if __name__=="__main__":unittest.main()
