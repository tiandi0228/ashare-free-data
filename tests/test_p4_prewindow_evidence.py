import copy
import json
import unittest
import hashlib
from unittest.mock import patch

from collector.p4_prewindow_evidence import (
    HEAD, JOB, REPO, RUN, WORKFLOW, instant, verify,
)

class PrewindowEvidenceTests(unittest.TestCase):
    def setUp(self):
        registration = {"protocol": {"claimed_created_at_utc": "2026-11-13T09:50:11Z",
                                     "window_start": "2026-12-01", "window_end": "2027-01-31"}}
        self.fingerprint = hashlib.sha256(json.dumps(
            registration, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.raw = json.dumps({"registration": registration, "registration_sha256": self.fingerprint})
        self.enterContext(patch("collector.p4_prewindow_evidence.MANIFEST_DIGEST", self.fingerprint))
        self.run = dict(id=RUN, head_sha=HEAD, path=WORKFLOW, workflow_id=417115300,
                        event="pull_request", run_attempt=1, status="completed", conclusion="success",
                        repository={"full_name": REPO}, created_at="2026-11-13T09:51:40Z",
                        run_started_at="2026-11-13T09:51:40Z")
        self.job = dict(id=JOB, run_id=RUN, head_sha=HEAD, name="verify-registration",
                        status="completed", conclusion="success", started_at="2026-11-13T09:51:42Z",
                        completed_at="2026-11-13T09:52:03Z", steps=[
                            dict(name=name, status="completed", conclusion="success",
                                 started_at=start, completed_at=end)
                            for name, start, end in [
                                ("Validate frozen rules and time boundaries",
                                 "2026-11-13T09:51:46Z", "2026-11-13T09:51:47Z"),
                                ("Independently reproduce registered baseline bytes",
                                 "2026-11-13T09:51:47Z", "2026-11-13T09:52:01Z"),
                            ]
                        ])

    def test_corroboration_never_authorizes_trade_or_claims_capture(self):
        result = verify(self.run, self.job, self.raw)
        self.assertEqual(result["registration_sha256"], self.fingerprint)
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])
        self.assertFalse(result["sample_capture_started"])
        self.assertFalse(result["prospective_OOS_validated"])

    def test_replayed_run_attempt_and_wrong_commit_are_rejected(self):
        for changes in ({"run_attempt": 2}, {"head_sha": "0" * 40}, {"conclusion": "failure"}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "workflow identity"):
                verify(dict(self.run, **changes), self.job, self.raw)

    def test_job_completion_at_beijing_midnight_is_too_late(self):
        with self.assertRaisesRegex(ValueError, "before the Beijing window"):
            verify(self.run, dict(self.job, completed_at="2026-11-30T16:00:00Z"), self.raw)

    def test_required_steps_must_succeed_once_and_be_ordered(self):
        for mode in ("missing", "failed", "unordered"):
            job = copy.deepcopy(self.job)
            if mode == "missing":
                job["steps"].pop()
            elif mode == "failed":
                job["steps"][1]["conclusion"] = "failure"
            else:
                job["steps"][1]["started_at"] = "2026-11-13T09:51:45Z"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify(self.run, job, self.raw)

    def test_tampered_manifest_is_rejected(self):
        doc = json.loads(self.raw)
        doc["registration"]["protocol"]["window_start"] = "2027-01-01"
        with self.assertRaisesRegex(ValueError, "manifest"):
            verify(self.run, self.job, json.dumps(doc))

    def test_noncanonical_provider_timestamp_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "canonical UTC"):
            instant("2026-11-13T09:51:40+00:00")
