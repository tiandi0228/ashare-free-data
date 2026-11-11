import copy
import unittest
from collector.p3_publication_asof_gate import assess
from collector.p3_publication_proof_task_queue import build

DECISION = "2026-10-20T09:30:00+08:00"


def claim():
    return {
        "issuer": "sh.600421", "kind": "DELIST_EFFECTIVE",
        "original_sha256": "a"*64, "effective_date": "2026-10-20",
        "authenticated_first_published_at": "2026-10-19T08:00:00+08:00",
        "publisher_independently_authenticated": True,
        "original_bytes_verified": True,
        "publication_timestamp_independently_authenticated": True,
        "trade_gate": "BLOCKED", "orders": [],
    }


class ProofTaskQueueTests(unittest.TestCase):
    def test_gap_reasons_create_bounded_research_only_actions(self):
        examples = [
            ("original_bytes_verified", False, "ORIGINAL_BYTES_NOT_VERIFIED"),
            ("publisher_independently_authenticated", False, "PUBLISHER_NOT_AUTHENTICATED"),
            ("publication_timestamp_independently_authenticated", False, "FIRST_PUBLICATION_NOT_AUTHENTICATED"),
            ("authenticated_first_published_at", "2026-10-20T17:00:00+08:00", "PUBLICATION_AFTER_DECISION"),
            ("effective_date", "2026-10-21", "EFFECTIVE_DATE_AFTER_DECISION"),
        ]
        for field, value, reason in examples:
            with self.subTest(reason=reason):
                row = claim()
                row[field] = value
                result = build(assess([row], DECISION))
                self.assertEqual(result["task_count"], 1)
                self.assertEqual(result["tasks"][0]["missing_proof"], reason)
                self.assertEqual(result["trade_gate"], "BLOCKED")
                self.assertEqual(result["orders"], [])
                self.assertFalse(result["tasks"][0]["trade_eligible"])

    def test_known_event_never_unlocks_full_pit(self):
        result = build(assess([claim()], DECISION))
        self.assertEqual(result["tasks"][0]["research_action"],
                         "RECONCILE_FULL_OFFICIAL_ISSUER_DAY_STATE")
        self.assertFalse(result["historical_PIT_verified"])

    def test_empty_and_counter_tamper(self):
        base = assess([], DECISION)
        self.assertEqual(build(base)["task_count"], 0)
        row = assess([claim()], DECISION)
        row["publication_proof_status_counts"] = {}
        with self.assertRaises(ValueError):
            build(row)
        row = assess([claim()], DECISION)
        row["known_event_count"] = 0
        with self.assertRaises(ValueError):
            build(row)

    def test_reject_promoted_or_duplicate_events(self):
        base = assess([claim()], DECISION)
        for key, value in (
            ("certified_full_daily_state", True),
            ("known_before_decision", False),
            ("original_sha256", "broken"),
            ("publication_proof_status", "TRADE_OK"),
        ):
            row = copy.deepcopy(base)
            row["events"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build(row)
        row = assess([claim()], DECISION)
        row["events"].append(copy.deepcopy(row["events"][0]))
        row["publication_proof_status_counts"] = {
            "EVENT_KNOWN_FULL_DAILY_STATE_UNCERTIFIED": 2}
        row["known_event_count"] = 2
        with self.assertRaises(ValueError):
            build(row)


    def test_direct_queue_rejects_impossible_calendar_days(self):
        # A forged as-of report must not bypass the date check in assess().
        for bad in ("2026-02-30", "2026-13-01", "2026-00-01"):
            report = assess([claim()], DECISION)
            report["events"][0]["effective_date"] = bad
            with self.subTest(day=bad), self.assertRaisesRegex(
                    ValueError, "invalid candidate event calendar day"):
                build(report)

    def test_same_original_sha_distinct_text_dates_remain_separate_tasks(self):
        a=claim()
        b=claim();b["effective_date"]="2026-10-21"
        result=build(assess([a,b],DECISION))
        self.assertEqual(result["task_count"],2)
        self.assertEqual(
            {x["candidate_text_day_unverified"] for x in result["tasks"]},
            {"2026-10-20","2026-10-21"})
        self.assertTrue(all(x["trade_eligible"] is False for x in result["tasks"]))
        self.assertFalse(result["historical_PIT_verified"])

if __name__ == "__main__":
    unittest.main()
