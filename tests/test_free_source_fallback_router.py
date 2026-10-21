"""Actual cloud source-receipt route classification, strictly research-only."""
import copy
import json
from pathlib import Path
import unittest

from collector.free_source_fallback_router import evaluate

ROOT = Path(__file__).resolve().parents[1] / "reports"

class RouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=[
            json.loads((ROOT/name).read_text(encoding="utf-8"))
            for name in (
                "p1_pilot_16_source_digests_20261021.json",
                "p1_vendor_lifecycle_20261021.json",
                "p3_cninfo_600421_early_20261021.json",
                "p3_cninfo_600421_disclosure_pdf_20261021.json",
            )
        ]

    def checked(self,overrides=None):
        inputs=copy.deepcopy(self.records)
        if overrides:
            overrides(inputs)
        return evaluate(*inputs)

    def test_free_provider_fallback_does_not_unlock_exchange_status(self):
        x=self.checked()
        self.assertEqual(x["status"],"RESEARCH_ONLY_NO_AUTHENTICATED_EXCHANGE_STATUS")
        self.assertEqual([p["selected_free_source"] for p in x["source_routes"]],
                         ["Baostock","Baostock query_stock_basic","CNINFO static issuer PDF",None])
        self.assertEqual(x["trade_gate"],"BLOCKED")
        self.assertEqual(x["candidate_universe"],[])
        self.assertEqual(x["executable_candidates"],[])
        self.assertEqual(x["orders"],[])
        self.assertEqual(x["paid_api_calls"],0)
        self.assertFalse(x["historical_point_in_time_universe_verified"])
        self.assertFalse(x["source_routes"][3]["suitable_for_formal_P3_status"])
        self.assertFalse(x["source_substitution_policy"]["automatic_paid_fallback"])

    def test_marketwide_cannot_be_forged(self):
        def tamper(x):
            x[0]["audit_report"]["market_wide_backfill_complete"]=True
        with self.assertRaisesRegex(ValueError,"research-only"):
            self.checked(tamper)

    def test_vendor_hindsight_cannot_be_promoted(self):
        def tamper(x):
            x[1]["source_report"]["historical_point_in_time_universe_verified"]=True
        with self.assertRaisesRegex(ValueError,"lifecycle"):
            self.checked(tamper)

    def test_mismatched_issuer_pdf_identity_rejected(self):
        def tamper(x):
            x[2]["source_observation"]["source_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"Issuer disclosure"):
            self.checked(tamper)

    def test_fake_sse_original_credential_rejected(self):
        def tamper(x):
            x[3]["sse_original_sha_not_obtained"]=False
        with self.assertRaisesRegex(ValueError,"Issuer disclosure"):
            self.checked(tamper)

    def test_wrong_source_run_rejected(self):
        def tamper(x):
            x[0]["capture_run_ids"]=[1,2]
        with self.assertRaisesRegex(ValueError,"Market-history"):
            self.checked(tamper)


if __name__=="__main__":
    unittest.main()
