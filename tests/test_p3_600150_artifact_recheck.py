"""Regression tests for the P3 600150 research-only PDF artifact verifier."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from collector.p3_600150_artifact_recheck import recheck, EXPECTED, SOURCE, CSV_SHA


def fixture(root):
    (root / "originals").mkdir(parents=True)
    rows = []
    for i, (identifier, (kind, number, url)) in enumerate(EXPECTED.items()):
        raw = b"%PDF-1.4\n" + bytes([65+i])*3000 + b"\n%%EOF\n"
        digest = hashlib.sha256(raw).hexdigest()
        rel = f"originals/sh_600150_{identifier}_{digest}.pdf"
        (root / rel).write_bytes(raw)
        rows.append(dict(issuer="sh.600150", document_role=kind,
                         announcement_id=identifier, notice_number_claimed=number,
                         requested_url=url, status="ORIGINAL_BYTES_SHA_REPLAY_VERIFIED_RESEARCH_ONLY",
                         pdf_sha256=digest, original_pdf_bytes=len(raw), original_artifact_path=rel,
                         first_publication_authenticated=False,
                         official_publisher_authenticated_independently=False,
                         historical_effective_date_authenticated=False))
    data = dict(phase="P3_600150_TWO_CNINFO_ORIGINAL_RESEARCH_ACQUISITION",
                source_issuer="sh.600150", frozen_vendor_source_commit=SOURCE,
                frozen_vendor_csv_sha256=CSV_SHA, documents_attempted=2,
                documents_pdf_sha_replayed=2, documents=rows,
                research_only_not_certified=True, originals_in_immutable_git_archive=False,
                trade_gate="BLOCKED", orders=[], executable_candidates=[],
                broker_fills_verified=0, official_first_publication_authenticated=False,
                official_halt_resume_interval_certified=False,
                official_historical_PIT_verified=False, trading_calendar_verified=False)
    (root / "receipt.json").write_text(json.dumps(data))
    return data


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/"artifact"
        self.data = fixture(self.root)

    def update(self):
        (self.root/"receipt.json").write_text(json.dumps(self.data))

    def test_good_replay_blocked(self):
        result = recheck(self.root)
        self.assertEqual(result["verified_originals"], 2)
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertFalse(result["official_historical_PIT_verified"])

    def test_tampered_pdf_rejected(self):
        pdf = self.root / self.data["documents"][0]["original_artifact_path"]
        pdf.write_bytes(pdf.read_bytes().replace(b"AAAA", b"BBBB"))
        with self.assertRaises(ValueError): recheck(self.root)

    def test_forged_authentication_rejected(self):
        self.data["documents"][0]["first_publication_authenticated"] = 1
        self.update()
        with self.assertRaises(ValueError): recheck(self.root)

    def test_duplicate_claim_rejected(self):
        self.data["documents"][1] = self.data["documents"][0].copy()
        self.update()
        with self.assertRaises(ValueError): recheck(self.root)

    def test_extra_file_rejected(self):
        (self.root/"originals"/"extra.pdf").write_bytes(b"fake")
        with self.assertRaises(ValueError): recheck(self.root)

    def test_promoted_pit_rejected(self):
        self.data["official_historical_PIT_verified"] = True
        self.update()
        with self.assertRaises(ValueError): recheck(self.root)

    def test_path_traversal_rejected(self):
        self.data["documents"][0]["original_artifact_path"] = "../../other.pdf"
        self.update()
        with self.assertRaises(ValueError): recheck(self.root)

    def test_gate_change_rejected(self):
        self.data["trade_gate"] = "OPEN"
        self.update()
        with self.assertRaises(ValueError): recheck(self.root)
