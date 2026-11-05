"""P3 review packets preserve source proof gaps, never certify market state."""
import copy
import unittest

from collector.p3_event_proof_gap_queue import build as queue_build
from collector.p3_proof_gap_triage import build as triage_build
from collector.p3_official_review_packets import build
from tests.test_p3_event_proof_gap_queue import fixture


def sample():
    return triage_build(queue_build(fixture()))


class OfficialReviewPacketsTests(unittest.TestCase):
    def test_all_categories_preserved_with_original_sha_and_notice(self):
        report=build(sample())
        self.assertEqual(report["total_review_tasks"],5)
        self.assertEqual(report["review_bucket_counts"],{
            "CONFLICT_REQUIRES_ORIGINAL_REVIEW":1,
            "INDEPENDENT_TIME_AND_INTERVAL_EVIDENCE":1,
            "MISSING_HALT_SOURCE":1,
            "MISSING_RESUMPTION_SOURCE":2,
        })
        paired=next(r for r in report["tasks"]
                    if r["review_bucket"]=="INDEPENDENT_TIME_AND_INTERVAL_EVIDENCE")
        self.assertEqual([s["original_pdf_sha256"] for s in
            paired["archived_research_originals_not_publication_proof"]],
            ["a"*64,"b"*64])
        self.assertEqual(paired["archived_research_originals_not_publication_proof"][0][
            "original_archive_path"],"pdf/sh_600001/111/"+"a"*64+".pdf")
        conflict=report["tasks"][0]
        self.assertEqual(len(conflict["archived_research_originals_not_publication_proof"]),2)
        orphan=next(r for r in report["tasks"] if r["review_bucket"]=="MISSING_HALT_SOURCE")
        self.assertEqual(orphan["archived_research_originals_not_publication_proof"],[])
        self.assertEqual(orphan["source_limitations"],
                         "UNPAIRED_RESUMPTION_TEXT_UNPINNED_IN_SOURCE_QUEUE")
        self.assertTrue(all(r["review_status"]=="NEEDS_INDEPENDENT_OFFICIAL_EVIDENCE"
                            and not r["historical_PIT_verified"] and not r["trade_eligible"]
                            for r in report["tasks"]))
        self.assertFalse(report["historical_PIT_verified"])
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])
    def test_reproducible_source_ids(self):
        self.assertEqual([r["task_id"] for r in build(sample())["tasks"]],
                         [r["task_id"] for r in build(sample())["tasks"]])
    def test_tampered_sha_and_original_locator_fail_closed(self):
        src=sample()
        mutations=(
            lambda x:x.update(trade_gate="OPEN"),
            lambda x:x.update(official_state_intervals_certified=1),
            lambda x:x["work_items"].pop(),
            lambda x:x["work_items"][1]["original_research_review_evidence"].update(
                halt_pdf_sha256="0"*64),
            lambda x:x["work_items"][1]["original_research_review_evidence"][
                "halt_original_archive_capture"].update(
                    sha_verified_original_archive_path="forged.pdf"),
            lambda x:x["work_items"][0]["original_research_review_evidence"].update(
                same_announcement_id_reused_in_halt_conflict=True),
            lambda x:x["work_items"][1].update(
                official_evidence_status="AUTHENTICATED"),
            lambda x:x["work_items"][1].update(
                eligible_for_historical_trade_replay=True),
            lambda x:x["work_items"][1].update(queue_index=9),
        )
        for change in mutations:
            with self.subTest(change=change):
                bad=copy.deepcopy(src)
                change(bad)
                with self.assertRaises(ValueError):
                    build(bad)


if __name__=="__main__":
    unittest.main()
