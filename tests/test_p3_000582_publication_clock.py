import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from collector.p3_000582_publication_clock import inspect


class PublicationClockTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads(Path("tests/fixtures/p3/000582-cninfo-index.json").read_bytes())
        self.pdfs = {"halt": b"halt", "resume": b"resume"}
        self.digests = {k: ("", hashlib.sha256(v).hexdigest()) for k, v in self.pdfs.items()}
        self.enterContext(patch("collector.p3_000582_publication_clock.SOURCES", self.digests))

    def test_midnight_and_media_date_do_not_certify_first_publication(self):
        r = inspect(self.rows, self.pdfs)
        self.assertTrue(all(n["index_value_is_midnight"] for n in r["notices"].values()))
        self.assertFalse(any(n["first_publication_time_verified"] for n in r["notices"].values()))
        self.assertEqual(r["media_context_not_official_notice_clock"]["report_date_beijing"], "2026-10-11")
        self.assertFalse(r["historical_decision_time_eligibility_verified"])
        self.assertEqual(r["trade_gate"], "BLOCKED")

    def test_non_midnight_still_does_not_certify(self):
        self.rows[0]["announcementTime"] += 60000
        r = inspect(self.rows, self.pdfs)
        self.assertFalse(r["notices"]["resume"]["index_value_is_midnight"])
        self.assertFalse(r["notices"]["resume"]["first_publication_time_verified"])

    def test_rejects_wrong_path_duplicate_and_changed_bytes(self):
        bad = self.rows[0] | {"adjunctUrl": "finalpage/2026-10-12/9999999999.PDF"}
        for rows, pdfs in (([bad, self.rows[1]], self.pdfs), ([self.rows[0]] * 2, self.pdfs),
                           (self.rows, self.pdfs | {"halt": b"changed"})):
            with self.assertRaises(ValueError):
                inspect(rows, pdfs)
