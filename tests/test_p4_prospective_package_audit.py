import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from collector.p4_prospective_daily_capture import CODES, END, REGISTRATION, START, capture
from collector.p4_prospective_package_audit import (
    EVIDENCE, PREFIX, PROOF_COMMIT, PROOF_JOB, PROOF_RUN, audit,
)
from tests.test_p4_prospective_daily_capture import FIRST, Provider

DAY = "2026-12-01"


class PackageAuditTests(unittest.TestCase):
    def build(self, root, mode="normal", mutation=None):
        capture(root, FIRST, lambda: Provider(mode))
        proof = {
            "status": "GITHUB_PREWINDOW_RUN_CORROBORATED_RESEARCH_ONLY",
            "registration_sha256": REGISTRATION, "registration_commit": PROOF_COMMIT,
            "github_run_id": PROOF_RUN, "github_job_id": PROOF_JOB,
            "window_starts_beijing": START.isoformat() + "T00:00:00+08:00",
            "window_ends_beijing_inclusive": END.isoformat(),
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
            "prospective_OOS_validated": False, "historical_PIT_verified": False,
            "historical_OOS_validated": False,
        }
        entries = {EVIDENCE: json.dumps(proof).encode()}
        entries.update({f"{PREFIX}/{DAY}/{p.name}": p.read_bytes()
                        for p in (root / DAY).iterdir()})
        if mutation:
            mutation(entries)
        path = root / "capture.zip"
        with ZipFile(path, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return path

    def test_full_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit(self.build(Path(tmp)), DAY)
            self.assertTrue(result["pilot_complete"])
            self.assertEqual(result["verified_vendor_rows"], 8)
            self.assertEqual(result["trade_gate"], "BLOCKED")
            self.assertFalse(result["github_origin_independently_verified"])

    def test_partial_missing_and_suspended_are_distinct(self):
        for mode, missing, suspended in (("partial", [CODES[-1]], []),
                                          ("missing", list(CODES), []),
                                          ("suspended", [], list(CODES))):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                result = audit(self.build(Path(tmp), mode), DAY)
                self.assertEqual(result["missing_vendor_issuers"], missing)
                self.assertEqual(result["vendor_suspended_issuers"], suspended)

    def test_csv_tampering(self):
        name = f"{PREFIX}/{DAY}/sh_601100.csv"
        with tempfile.TemporaryDirectory() as tmp:
            path = self.build(Path(tmp), mutation=lambda e: e.update({name: b"changed"}))
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                audit(path, DAY)

    def test_wrong_expected_day_or_unexpected_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "unexpected"):
                audit(self.build(Path(tmp)), "2026-12-02")
        with tempfile.TemporaryDirectory() as tmp:
            path = self.build(Path(tmp), mutation=lambda e: e.update({"../extra": b"x"}))
            with self.assertRaisesRegex(ValueError, "unexpected"):
                audit(path, DAY)

    def test_missing_or_forged_registration(self):
        for mutate in (lambda e: e.pop(EVIDENCE), lambda e: e.update({EVIDENCE: b"{}"})):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ValueError, "registration evidence"):
                    audit(self.build(Path(tmp), mutation=mutate), DAY)
