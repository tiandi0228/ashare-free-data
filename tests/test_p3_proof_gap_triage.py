"""Offline regression for P3 official-proof gap triage; never opens trade gate."""
import copy
import unittest
from collector.p3_event_proof_gap_queue import build as queue_build
from collector.p3_proof_gap_triage import build
from tests.test_p3_event_proof_gap_queue import fixture


class P3GapTriageTests(unittest.TestCase):
    def test_reconciles_all_queue_rows_and_keeps_gate_blocked(self):
        result = build(queue_build(fixture()))
        self.assertEqual(result["total_unresolved_work_items"], 5)
        self.assertEqual(result["review_bucket_counts"], {
            "CONFLICT_REQUIRES_ORIGINAL_REVIEW": 1,
            "INDEPENDENT_TIME_AND_INTERVAL_EVIDENCE": 1,
            "MISSING_HALT_SOURCE": 1,
            "MISSING_RESUMPTION_SOURCE": 2,
        })
        self.assertEqual([x["priority"] for x in result["work_items"]], [0, 1, 2, 2, 3])
        self.assertTrue(all(x["official_evidence_status"] == "NOT_AUTHENTICATED"
                            and x["eligible_for_historical_trade_replay"] is False
                            for x in result["work_items"]))
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])
        self.assertFalse(result["historical_PIT_verified"])

    def test_source_sha_and_archive_review_anchors_survive_triage(self):
        queue = queue_build(fixture())
        report = build(queue)
        by_kind = {r["source_kind"]: r for r in report["work_items"]}
        paired = by_kind["PAIRED_UNCERTIFIED_HALT_RESUME"]
        evidence = paired["original_research_review_evidence"]
        self.assertEqual(evidence["halt_pdf_sha256"], "a" * 64)
        self.assertEqual(evidence["resume_pdf_sha256"], "b" * 64)
        self.assertEqual(evidence["halt_announcement_id"], "111")
        self.assertEqual(
            evidence["halt_original_archive_capture"]["sha_verified_original_archive_path"],
            "pdf/sh_600001/111/" + "a" * 64 + ".pdf")
        self.assertTrue(paired["original_research_is_not_first_publication_proof"])
        conflict = by_kind["CONFLICTING_HALTS_MANUAL_REVIEW_FIRST"]
        self.assertEqual(
            conflict["original_research_review_evidence"][
                "previous_halt_original_sha_and_text_day_candidates"][0][
                    "original_pdf_sha256"], "e" * 64)
        self.assertFalse(conflict["eligible_for_historical_trade_replay"])
        evidence["halt_original_archive_capture"]["first_archived_original_run_id"] = 9999
        self.assertEqual(
            queue["work_items"][1]["halt_original_archive_capture"][
                "first_archived_original_run_id"], 151)

    def test_missing_required_original_anchor_fails_closed(self):
        q = queue_build(fixture())
        q["work_items"][1].pop("halt_original_archive_capture")
        with self.assertRaises(ValueError):
            build(q)

    def test_rejects_forged_certification_and_missing_items(self):
        original = queue_build(fixture())
        mutations = (
            lambda q: q.update(trade_gate="OPEN"),
            lambda q: q.update(historical_PIT_verified=True),
            lambda q: q.update(certified_issuer_state_intervals=1),
            lambda q: q.update(official_first_publication_authenticated_from_capture=1),
            lambda q: q["work_items"].pop(),
            lambda q: q["work_items"][0].update(trade_eligible=True),
            lambda q: q["work_items"][0].update(priority=2),
            lambda q: q["work_items"][0].update(kind="UNKNOWN"),
            lambda q: q["work_items"][0].update(missing_independent_proofs=[]),
            lambda q: q.update(recommendations=[{"buy": True}]),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                sample = copy.deepcopy(original)
                mutate(sample)
                with self.assertRaises(ValueError):
                    build(sample)

    def test_zero_items_is_not_pit_certification(self):
        source = fixture()
        for key in ("research_text_event_claims", "paired_event_texts",
                    "official_resumption_followups", "orphan_resume_texts",
                    "overlap_conflicts"):
            source[key] = []
        for key in ("raw_text_assertion_references",
                    "deduplicated_text_event_claims",
                    "unpaired_halt_starts_needing_resumption_search",
                    "paired_halt_resume_text_claims_unverified",
                    "unpaired_resume_claims",
                    "overlapping_halt_claims_without_resume",
                    "approval_consent_is_not_effective_date_count"):
            source[key] = 0
        result = build(queue_build(source))
        self.assertEqual(result["total_unresolved_work_items"], 0)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["trade_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
