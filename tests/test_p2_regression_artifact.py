import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from collector.p2_gap_disposition import compare
from collector.p2_regression_artifact import DISPOSITION, RECEIPT, REPLAY, verify


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "result.zip"
        self.pin = dict(asof="2026-10-20", source_epoch_sha256="epoch", entries={})
        replay = dict(phase="P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS",
                      status="SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY",
                      trade_gate="BLOCKED", orders=[], executable_candidates=[], coverage_gaps_resolved=0,
                      historical_PIT_verified=False, asof_completed_day=self.pin["asof"],
                      source_epoch_sha256="epoch", research_gap_issuers=0, results=[])
        self.disp = compare(replay, self.pin)
        self.reports = {REPLAY: json.dumps(replay), DISPOSITION: json.dumps(self.disp)}

    def bundle(self, tamper=False, extra=False):
        keys = ("asof", "source_epoch_sha256", "explained_feature_unavailable",
                "review_required", "feature_gaps_resolved")
        rec = {k: self.disp[k] for k in keys}
        rec.update(kind="PINNED_ARCHIVE_REGRESSION_NOT_LIVE_COVERAGE", archive_commit="commit",
                   github_run_id="42", github_run_attempt="1", tested_commit="merge-sha",
                   trade_gate="BLOCKED", historical_PIT_verified=False,
                   report_sha256={k: hashlib.sha256(v.encode()).hexdigest() for k, v in self.reports.items()})
        with ZipFile(self.path, "w") as z:
            for k, v in self.reports.items():
                z.writestr(k, v + (" " if tamper else ""))
            z.writestr(RECEIPT, json.dumps(rec))
            if extra:
                z.writestr("extra", "unexpected")

    def verify_bundle(self, **overrides):
        expected = dict(expected_archive_commit="commit", expected_run_id="42",
                        expected_run_attempt="1", expected_tested_commit="merge-sha",
                        expected_zip_sha256="sha256:" + hashlib.sha256(self.path.read_bytes()).hexdigest())
        return verify(self.path, self.pin, **(expected | overrides))

    def test_valid_provenance(self):
        self.bundle()
        result = self.verify_bundle()
        self.assertEqual(result["feature_gaps_resolved"], 0)
        self.assertEqual((result["tested_commit"], result["github_run_attempt"]), ("merge-sha", "1"))

    def test_reject_stale_or_wrong_provenance(self):
        self.bundle()
        for field, wrong in (("expected_run_id", "43"), ("expected_run_attempt", "2"),
                             ("expected_tested_commit", "pr-head"), ("expected_archive_commit", "other")):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "scope"):
                self.verify_bundle(**{field: wrong})

    def test_reject_zip_digest_mismatch(self):
        self.bundle()
        with self.assertRaisesRegex(ValueError, "ZIP SHA-256"):
            self.verify_bundle(expected_zip_sha256="0" * 64)

    def test_modified_report_and_extra_file(self):
        self.bundle(tamper=True)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.verify_bundle()
        self.bundle(extra=True)
        with self.assertRaisesRegex(ValueError, "contents"):
            self.verify_bundle()

    def test_rehashed_disposition_still_requires_replay(self):
        self.reports[DISPOSITION] = json.dumps(dict(self.disp, review_required=1))
        self.bundle()
        with self.assertRaisesRegex(ValueError, "replay mismatch"):
            self.verify_bundle()
