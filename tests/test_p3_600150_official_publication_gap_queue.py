"""Fail-closed P3 official-publication gap queue regressions."""
import copy
import unittest
from collector.p3_600150_official_publication_gap_queue import (
    CSV_SHA, PDFS, SOURCE_COMMIT, REQUIRED_GAPS, queue,
)


def sample():
    rows = []
    for ident, spec in PDFS.items():
        rows.append({
            "issuer": "sh.600150", "announcement_id": ident,
            "document_role": spec["role"],
            "notice_number_claimed": spec["number"],
            "requested_url": spec["url"],
            "pdf_sha256": spec["sha256"],
            "original_pdf_bytes": spec["bytes"],
            "status": "ORIGINAL_BYTES_SHA_REPLAY_VERIFIED_RESEARCH_ONLY",
            "original_artifact_path": f"originals/sh_600150_{ident}_{spec['sha256']}.pdf",
            "observed_utc": "2026-11-12T01:24:22+00:00",
            "first_publication_authenticated": False,
            "official_publisher_authenticated_independently": False,
            "historical_effective_date_authenticated": False,
        })
    return {
        "phase": "P3_600150_TWO_CNINFO_ORIGINAL_RESEARCH_ACQUISITION",
        "source_issuer": "sh.600150",
        "frozen_vendor_source_commit": SOURCE_COMMIT,
        "frozen_vendor_csv_sha256": CSV_SHA,
        "documents_attempted": 2,
        "documents_pdf_sha_replayed": 2,
        "broker_fills_verified": 0,
        "documents": rows,
        "research_only_not_certified": True,
        "originals_in_immutable_git_archive": False,
        "official_first_publication_authenticated": False,
        "official_halt_resume_interval_certified": False,
        "official_historical_PIT_verified": False,
        "trading_calendar_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


class GapQueueTests(unittest.TestCase):
    def setUp(self):
        self.data = sample()

    def rejected(self):
        with self.assertRaises(ValueError):
            queue(self.data)

    def test_two_pinned_proof_tasks_stay_blocked(self):
        result = queue(self.data)
        self.assertEqual(result["research_original_count"], 2)
        self.assertEqual(result["official_publication_instants_authenticated"], 0)
        self.assertEqual(result["official_state_intervals_certified"], 0)
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])
        self.assertTrue(all(t["missing_official_proofs"] == list(REQUIRED_GAPS)
                            for t in result["proof_tasks"]))

    def test_duplicate_original_rejected(self):
        self.data["documents"][1] = copy.deepcopy(self.data["documents"][0])
        self.rejected()

    def test_wrong_digest_rejected(self):
        self.data["documents"][0]["pdf_sha256"] = "0" * 64
        self.rejected()

    def test_wrong_pinned_csv_rejected(self):
        self.data["frozen_vendor_csv_sha256"] = "a" * 64
        self.rejected()

    def test_forged_publisher_auth_rejected(self):
        self.data["documents"][0]["official_publisher_authenticated_independently"] = 1
        self.rejected()

    def test_forged_historical_auth_rejected(self):
        self.data["official_historical_PIT_verified"] = True
        self.rejected()

    def test_research_capture_not_publication(self):
        self.data["documents"][0]["observed_utc"] = "2026-11-13T02:00:00+08:00"
        result = queue(self.data)
        task = next(t for t in result["proof_tasks"] if t["announcement_id"] == "1224387134")
        self.assertEqual(task["capture_observed_utc_not_first_publication"], "2026-11-12T18:00:00+00:00")
        self.assertFalse(task["historical_first_publication_authenticated"])

    def test_naive_capture_rejected(self):
        self.data["documents"][0]["observed_utc"] = "2025-08-05T10:00:00"
        self.rejected()

    def test_any_trade_orders_rejected(self):
        self.data["orders"] = [{"buy": 1}]
        self.rejected()

    def test_fake_verified_counts_rejected(self):
        self.data["documents_pdf_sha_replayed"] = True
        self.rejected()

    def test_archive_promotion_rejected(self):
        self.data["originals_in_immutable_git_archive"] = True
        self.rejected()

    def test_missing_document_rejected(self):
        self.data["documents"] = self.data["documents"][:1]
        self.rejected()
