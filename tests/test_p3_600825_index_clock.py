import json
import unittest

from collector.p3_600825_index_clock import SOURCE, replay


class IndexClockTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads(SOURCE.read_bytes())

    def test_four_midnight_fields_do_not_attest_release(self):
        result = replay(self.receipt)
        self.assertEqual(len(result["rows"]), 4)
        self.assertTrue(all(x["classification"] == "MIDNIGHT_DATE_LABEL_ONLY"
                            and x["official_first_release"] is None for x in result["rows"]))
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_non_midnight_field_is_not_first_release_either(self):
        self.receipt["rows"][0]["index_published_milliseconds_unverified"] += 3600000
        result = replay(self.receipt)
        self.assertEqual(result["rows"][0]["classification"], "INDEX_CLOCK_FIELD_NOT_FIRST_RELEASE_PROOF")
        self.assertFalse(result["rows"][0]["official_preopen_visibility_verified"])

    def test_missing_or_duplicate_notice_rejected(self):
        row = self.receipt["rows"].pop()
        with self.assertRaises(ValueError):
            replay(self.receipt)
        self.receipt["rows"].extend([row, row])
        with self.assertRaises(ValueError):
            replay(self.receipt)

    def test_mismatched_pdf_identity_rejected(self):
        self.receipt["rows"][0]["official_pdf_url"] += "?different"
        with self.assertRaisesRegex(ValueError, "URL mismatch"):
            replay(self.receipt)
