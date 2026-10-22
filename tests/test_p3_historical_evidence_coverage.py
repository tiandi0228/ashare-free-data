"""Bounded P3 completeness controls: never infer missing historical issuer states."""
import unittest
from collector.p3_historical_evidence_coverage import audit_coverage

def item(code="sh.600421",kind="listing",**changes):
    v={"code":code,"decision_date":"2026-06-22","kind":kind,
       "original_bytes_verified":True,"official_exchange_source_verified":True,
       "publication_instant_verified":True,"historical_asof_verified":True,
       "entire_decision_day_state_covered":True,
       "original_sha256":"a"*64,"publication_day":"2026-06-21",
       "publication_instant_utc":"2026-06-21T12:00:00Z"}
    v.update(changes)
    return v

class CoverageTests(unittest.TestCase):
    def test_missing_three_event_kinds_blocks(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item()])
        self.assertEqual((r["required_evidence_cells"],r["verified_evidence_cells"],r["missing_evidence_cells"]),(4,1,3))
        self.assertFalse(r["complete"]);self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_all_four_synthetic_complete_still_no_orders(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item(kind=k) for k in ("listing","st","halt","delisting")])
        self.assertTrue(r["complete"]);self.assertEqual(r["orders"],[])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_vendor_does_not_authenticate(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item(official_exchange_source_verified=False)])
        self.assertEqual(r["verified_evidence_cells"],0)
    def test_hindsight_publication_blocked(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item(publication_day="2026-06-23")])
        self.assertFalse(r["complete"])
    def test_no_original_bytes_blocked(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item(original_bytes_verified=False)])
        self.assertEqual(r["rejected_evidence_records"],1)
    def test_missing_authenticated_instant_rejected(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item(publication_instant_utc=None)])
        self.assertEqual(r["verified_evidence_cells"],0)
    def test_same_day_instant_not_proven_before_decision(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item(publication_day="2026-06-22",publication_instant_utc="2026-06-22T00:01:00Z")])
        self.assertEqual(r["verified_evidence_cells"],0)
    def test_malformed_timestamp_fails_closed(self):
        r=audit_coverage(["sh.600421"],["2026-06-22"],[item(publication_instant_utc="unknown")])
        self.assertFalse(r["complete"])
    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            audit_coverage(["sh.600421"],["2026-06-22"],[item(),item()])
    def test_duplicate_rejected_records_cannot_mask_conflict(self):
        bad=item(original_bytes_verified=False)
        good=item()
        with self.assertRaisesRegex(ValueError,"duplicate evidence"):
            audit_coverage(["sh.600421"],["2026-06-22"],[bad,good])
        with self.assertRaisesRegex(ValueError,"duplicate evidence"):
            audit_coverage(["sh.600421"],["2026-06-22"],[bad,bad])

    def test_chinext_and_star_are_not_mainboard(self):
        for code in ("sz.300750","sz.301001","sh.688981","sh.689009"):
            with self.subTest(code=code), self.assertRaisesRegex(ValueError,"invalid issuer id"):
                audit_coverage([code],["2026-06-22"],[])
    def test_mainboard_prefixes_are_allowed(self):
        for code in ("sh.600421","sh.601228","sh.603259","sh.605001",
                     "sz.000651","sz.001696","sz.002204","sz.003000"):
            with self.subTest(code=code):
                r=audit_coverage([code],["2026-06-22"],[])
                self.assertEqual(r["required_evidence_cells"],4)
                self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_scope_rejected(self):
        with self.assertRaisesRegex(ValueError,"outside"):
            audit_coverage(["sh.600421"],["2026-06-22"],[item(code="sh.600608")])
    def test_unknown_entire_market_not_assumed(self):
        r=audit_coverage(["sh.600421","sh.600608"],["2026-06-22"],[])
        self.assertEqual(r["required_evidence_cells"],8)
        self.assertEqual(r["missing_evidence_cells"],8)

if __name__=="__main__":
    unittest.main()
