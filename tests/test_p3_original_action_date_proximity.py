import unittest

from collector.p3_original_action_date_proximity import extract


def report(sample, date="2026年1月5日"):
    return {
        "phase": "P3_SIX_ORIGINAL_PDF_DATE_CONTEXT_INSPECTION",
        "trade_gate": "BLOCKED",
        "results": [
            {
                "event_family": "TRADING_HALT",
                "issuer": f"issuer-{i}",
                "source_id": f"source-{i}",
                "date_contexts": [{"date_text": date, "nearby_text_samples": [sample]}],
            }
            for i in range(6)
        ],
    }


class OriginalActionDateProximityTests(unittest.TestCase):
    def test_repeated_date_uses_closest_occurrence(self):
        date = "2026年1月5日"
        sample = date + "无关文字" * 60 + "公司股票自" + date + "起复牌"
        q = extract(report(sample))
        self.assertEqual(q["source_documents"], 6)
        self.assertEqual(q["date_candidates"], 6)
        self.assertEqual(q["dates_with_nearby_actions"], 6)
        self.assertEqual(q["candidates"][0]["nearby_action_labels"], ["RESUME"])
        self.assertEqual(q["certified_effective_state_transitions"], 0)
        self.assertEqual(q["historical_PIT_eligible"], 0)
        self.assertEqual(q["trade_gate"], "BLOCKED")
        self.assertEqual(q["orders"], [])
        self.assertEqual(q["executable_candidates"], [])

    def test_mismatched_date_still_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "date/context mismatched"):
            extract(report("公司股票2026年1月6日起复牌"))

    def test_multiple_opposing_actions_remain_uncertified(self):
        sample = "公司股票自2026年1月5日起停牌，后又于2026年1月5日起复牌"
        q = extract(report(sample))
        self.assertEqual(q["date_candidates_with_multiple_action_labels"], 6)
        self.assertEqual(q["certified_effective_state_transitions"], 0)
        self.assertEqual(q["trade_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
