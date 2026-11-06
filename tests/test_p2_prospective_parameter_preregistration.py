"""Frozen P2 candidate never certifies historical holdout post-hoc."""
import unittest
from collector.p2_prospective_parameter_preregistration import register
NAME="MA20_CROSS_UPWARD_COMPLETED_DAILY_BAR_RESEARCH_ONLY"
BASE=dict(source_commit="a"*40,hypothesis=NAME,
    fold_source_sha256="b"*64,
    validation_start="2026-12-01",validation_end="2027-02-01",
    evidence_created_at_utc="2026-11-06T01:00:00Z")
class PreregisterTests(unittest.TestCase):
    def test_prospective_candidate_deterministic_but_not_authenticated(self):
        a=register(**BASE)
        b=register(**BASE)
        self.assertEqual(a["status"],"PROSPECTIVE_CANDIDATE_NOT_EXTERNAL_TIME_ATTESTATION")
        self.assertEqual(a["parameter_candidate_sha256"],b["parameter_candidate_sha256"])
        self.assertEqual(len(a["parameter_candidate_sha256"]),64)
        self.assertFalse(a["prospective_freeze_externally_attested"])
        self.assertFalse(a["parameters_frozen_before_historical_holdout_verified"])
        self.assertFalse(a["historical_OOS_validated"])
        self.assertFalse(a["strategy_returns_computed"])
        self.assertEqual(a["orders"],[])
        self.assertEqual(a["trade_gate"],"BLOCKED")
    def test_backdated_historical_holdout_never_claims_pre_registration(self):
        q=register(**dict(BASE,validation_start="2026-07-08",
                          validation_end="2026-10-22"))
        self.assertEqual(q["status"],"RETROSPECTIVE_WINDOW_CANNOT_BE_FROZEN_AFTER_START")
        self.assertFalse(q["historical_OOS_validated"])
        self.assertNotIn("parameter_candidate_sha256",q)
        self.assertEqual(q["trade_gate"],"BLOCKED")
    def test_same_day_is_not_independently_early(self):
        q=register(**dict(BASE,validation_start="2026-11-06"))
        self.assertEqual(q["status"],"RETROSPECTIVE_WINDOW_CANNOT_BE_FROZEN_AFTER_START")
    def test_mutated_strategy_source_or_fold_changes_fingerprint(self):
        expected=register(**BASE)["parameter_candidate_sha256"]
        for change in [
            dict(source_commit="c"*40),dict(fold_source_sha256="d"*64),
            dict(validation_end="2027-03-01"),
        ]:
            q=register(**dict(BASE,**change))
            self.assertNotEqual(q["parameter_candidate_sha256"],expected)
    def test_unknown_hypothesis_and_corrupt_datetimes_block(self):
        for change in [
            dict(hypothesis="WINNING_STRATEGY"),
            dict(source_commit="main"),
            dict(fold_source_sha256="BAD"),
            dict(validation_start="2026-11-01",validation_end="2026-11-01"),
            dict(evidence_created_at_utc="2026-11-06T01:00:00+00:00"),
            dict(evidence_created_at_utc="2026-11-06T01:00:00Zbad"),
            dict(evidence_created_at_utc="garbage"),
        ]:
            with self.subTest(change=change):
                q=register(**dict(BASE,**change))
                self.assertEqual(q["status"],"REJECTED")
                self.assertEqual(q["trade_gate"],"BLOCKED")
                self.assertEqual(q["orders"],[])
if __name__=="__main__":unittest.main()
