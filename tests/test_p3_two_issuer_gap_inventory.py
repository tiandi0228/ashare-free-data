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

    def test_three_issuer_rollup_and_required_third_report(self):
        c = report("sz.002813", 3, 6, 8, "notices", "matched_rows")
        result = inventory(self.a, self.b, c, include_002813=True)
        self.assertEqual(result["matched_vendor_issuer_days"], 32)
        self.assertEqual(result["verified_notice_originals"], 10)
        self.assertEqual(result["issuer_gaps_closed"], 0)
        with self.assertRaisesRegex(ValueError, "report count"):
            inventory(self.a, self.b, include_002813=True)

    def test_four_issuer_rollup_and_no_time_promotion(self):
        c = report("sz.002813", 3, 6, 8, "notices", "matched_rows")
        d = report("sh.605303", 3, 11, 11, "notices", "matched_rows")
        result = inventory(self.a, self.b, c, d, include_605303=True)
        self.assertEqual(result["matched_vendor_issuer_days"], 43)
        self.assertEqual(result["verified_notice_originals"], 13)
        self.assertEqual(result["official_first_release_verified"], 0)
        self.assertEqual(result["issuer_gaps_closed"], 0)
        d["notices"][0]["official_first_release"] = "2026-09-12T00:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "first-release"):
            inventory(self.a, self.b, c, d, include_605303=True)

    def test_five_issuer_rollup_requires_correct_fifth_issuer(self):
        c = report("sz.002813", 3, 6, 8, "notices", "matched_rows")
        d = report("sh.605303", 3, 11, 11, "notices", "matched_rows")
        e = report("sz.002870", 3, 11, 14, "notices", "matched_rows")
        result = inventory(self.a, self.b, c, d, e, include_002870=True)
        self.assertEqual(result["matched_vendor_issuer_days"], 54)
        self.assertEqual(result["verified_notice_originals"], 16)
        self.assertEqual(result["official_first_release_verified"], 0)
        self.assertEqual(result["issuer_gaps_closed"], 0)
        with self.assertRaisesRegex(ValueError, "issuer"):
            inventory(self.a, self.b, c, d, d, include_002870=True)

    def test_six_issuer_rollup_preserves_unverified_publication_boundary(self):
        c = report("sz.002813", 3, 6, 8, "notices", "matched_rows")
        d = report("sh.605303", 3, 11, 11, "notices", "matched_rows")
        e = report("sz.002870", 3, 11, 14, "notices", "matched_rows")
        f = report("sh.603400", 3, 11, 17, "notices", "matched_rows")
        result = inventory(self.a, self.b, c, d, e, f, include_603400=True)
        self.assertEqual(result["matched_vendor_issuer_days"], 65)
        self.assertEqual(result["verified_notice_originals"], 19)
        self.assertEqual(result["official_first_release_verified"], 0)
        self.assertEqual(result["issuer_gaps_closed"], 0)
        with self.assertRaisesRegex(ValueError, "report count"):
            inventory(self.a, self.b, c, d, e, include_603400=True)
        f["notices"][0]["official_first_release"] = "2026-09-15T00:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "first-release"):
            inventory(self.a, self.b, c, d, e, f, include_603400=True)
