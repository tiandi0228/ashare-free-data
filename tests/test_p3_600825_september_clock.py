import json
from pathlib import Path
import unittest

from collector.p3_600825_september_clock import audit


class SeptemberClockTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(Path("evidence/p3_600825/september-start-clock.json").read_bytes())
        self.notice = dict(notice_id="1225552231", announcement_number="2026-014",
                           event_dates=dict(retrospective_halt_start="2026-09-07",
                                            continued_halt="2026-09-08"))

    def test_reviewed_secondary_sources_remain_scoped(self):
        result = audit(self.source, self.notice)
        self.assertFalse(result["initial_halt_before_auction_verified"])
        self.assertFalse(result["official_first_release_verified"])
        self.assertEqual(result["earliest_reviewed_continuation_media_time"], "2026-09-07T19:09:00+08:00")
        self.assertEqual([x["initial_halt_classification"] for x in result["observations"]],
                         ["OMISSION_NOT_PROOF"] * 2 + ["RETROSPECTIVE_ONLY"] * 2 + ["NO_PUBLICATION_CLOCK"])

    def test_auction_cutoff_is_strict(self):
        row = self.source["observations"][2]
        self.source["observations"] = [row]
        for stamp, label in [
            ("2026-09-07T09:14:59+08:00", "SECONDARY_BEFORE_AUCTION_REQUIRES_REVIEW"),
            ("2026-09-07T09:15:00+08:00", "NOT_BEFORE_AUCTION"),
        ]:
            row["displayed_time"] = stamp
            result = audit(self.source, self.notice)
            self.assertEqual(result["observations"][0]["initial_halt_classification"], label)
            self.assertFalse(result["initial_halt_before_auction_verified"])

    def test_fail_closed_on_mismatched_notice(self):
        self.notice["notice_id"] = "1225602155"
        with self.assertRaisesRegex(ValueError, "source/notice"):
            audit(self.source, self.notice)

    def test_reject_effective_time_substituted_for_publication(self):
        row = self.source["observations"][-1]
        row["displayed_time"] = row["effective_start"]
        with self.assertRaisesRegex(ValueError, "must not supply"):
            audit(self.source, self.notice)
