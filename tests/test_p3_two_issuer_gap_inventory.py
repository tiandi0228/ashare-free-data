import unittest

from collector.p3_two_issuer_gap_inventory import inventory


def report(issuer, count, days, start, field, day_field):
    return {"issuer": issuer, "trade_gate": "BLOCKED", "historical_PIT_verified": False,
            "entire_issuer_gap_closed": False, "orders": [], "executable_candidates": [],
            day_field: days, field: [{"original_sha256": f"{n:064x}", "official_first_release": None}
                                    for n in range(start, start + count)]}


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.a = report("sh.600825", 4, 15, 1, "rows", "matched_vendor_days")
        self.b = report("sz.002860", 3, 11, 5, "notices", "matched_rows")

    def test_combines_without_closing_gaps(self):
        result = inventory(self.a, self.b)
        self.assertEqual(result["matched_vendor_issuer_days"], 26)
        self.assertEqual(result["verified_notice_originals"], 7)
        self.assertEqual(result["official_first_release_verified"], 0)
        self.assertEqual(result["issuer_gaps_closed"], 0)
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_rejects_duplicate_original(self):
        self.b["notices"][0]["original_sha256"] = self.a["rows"][0]["original_sha256"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            inventory(self.a, self.b)

    def test_rejects_clock_promotion_and_gap_closure(self):
        self.a["rows"][0]["official_first_release"] = "2026-09-08T00:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "first-release"):
            inventory(self.a, self.b)
        self.a["rows"][0]["official_first_release"] = None
        self.b["entire_issuer_gap_closed"] = True
        with self.assertRaisesRegex(ValueError, "unsafe"):
            inventory(self.a, self.b)
