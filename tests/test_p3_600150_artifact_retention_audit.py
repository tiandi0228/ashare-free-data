"""P3 retention gating: fixed manifest, remote provenance and no PIT promotion."""
import copy
import json
import unittest
from pathlib import Path
from collector.p3_600150_artifact_retention_audit import audit

MANIFEST = Path(__file__).resolve().parents[1] / "evidence/p3_600150_research_artifact_retention_manifest.json"


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())
        self.remote = []
        for row in self.manifest["artifacts"]:
            self.remote.append({
                "id": row["artifact_id"],
                "expired": False,
                "digest": "sha256:" + row["artifact_zip_sha256"],
                "expires_at": row["expires_at"],
                "workflow_run": {"id": row["source_run_id"]},
            })
        self.now = "2026-11-12T02:30:00+00:00"

    def verify(self):
        return audit(self.manifest, self.remote, at=self.now)

    def fail(self):
        with self.assertRaises(ValueError):
            self.verify()

    def test_valid_temporary_not_durable(self):
        row = self.verify()
        self.assertEqual(row["artifact_count"], 2)
        self.assertEqual(row["original_pdf_count"], 3)
        self.assertEqual(row["original_pdf_bytes_frozen"], 216146)
        self.assertIs(row["original_pdf_bytes_in_permanent_archive"], False)
        self.assertEqual(row["trade_gate"], "BLOCKED")
        self.assertEqual(row["orders"], [])

    def test_original_sha_changed(self):
        self.manifest["artifacts"][0]["pdf_originals"][0]["sha256"] = "0" * 64
        self.fail()

    def test_pdf_size_changed(self):
        self.manifest["artifacts"][1]["pdf_originals"][0]["bytes"] += 1
        self.fail()

    def test_zip_digest_remote_mismatch(self):
        self.remote[0]["digest"] = "sha256:" + "0" * 64
        self.fail()

    def test_missing_or_duplicate_remote_metadata(self):
        self.remote = [self.remote[0], copy.deepcopy(self.remote[0])]
        self.fail()

    def test_stale_remote_expiry(self):
        self.remote[1]["expired"] = True
        self.fail()

    def test_asof_expiration(self):
        self.now = "2026-12-12T01:24:22+00:00"
        self.fail()

    def test_forged_durable_originals_rejected(self):
        self.manifest["original_pdf_bytes_in_permanent_archive"] = True
        self.fail()

    def test_forged_pit_rejected(self):
        self.manifest["historical_first_publication_authenticated"] = True
        self.fail()

    def test_trade_unblock_rejected(self):
        self.manifest["trade_gate"] = "OPEN"
        self.fail()

    def test_missing_pdf_claim_rejected(self):
        self.manifest["artifacts"][0]["pdf_originals"].pop()
        self.fail()

    def test_naive_asof_rejected(self):
        self.now = "2026-11-12T02:30:00"
        self.fail()
