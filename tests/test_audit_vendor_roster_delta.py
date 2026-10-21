"""Guard against hindsight/current-only historical issuer-pool survivorship."""
import copy
import hashlib
import unittest

from collector.audit_vendor_roster_delta import compare_rosters


EARLY=[
    ["sh.600000","1","浦发银行"],
    ["sh.603019","0","中科曙光"],
    ["sh.600421","1","退市前样本"],
]
LATE=[
    ["sh.600000","1","浦发银行"],
    ["sh.603019","1","中科曙光"],
    ["sh.600001","1","新增样本"],
]


class CohortDeltaTests(unittest.TestCase):
    def test_early_only_delisted_candidate_not_deleted_from_history(self):
        r=compare_rosters(EARLY,LATE,minimum_intersection=2)
        self.assertEqual((r["early_issuer_count"],r["late_issuer_count"]),(3,3))
        self.assertEqual(r["common_issuer_count"],2)
        self.assertEqual(r["early_only_count"],1)
        self.assertEqual(r["late_only_count"],1)
        self.assertEqual(r["combined_unique_issuer_codes"],4)
        self.assertTrue(r["sh_600421_present_in_early_snapshot"])
        self.assertFalse(r["sh_600421_present_in_late_snapshot"])
        self.assertEqual(r["vendor_status_changes_in_common_codes"]["0_to_1"],1)
        self.assertEqual(r["vendor_status_changes_in_common_codes"]["1_to_1"],1)
        self.assertFalse(r["membership_delta_proves_IPO_or_delisting"])
        self.assertFalse(r["retrospective_vendor_membership_is_PIT"])
        self.assertFalse(r["validated_exchange_event_effective_dates"])

    def test_date_inputs_order_changes_issuer_absence_not_legal_status(self):
        r=compare_rosters(LATE,EARLY,minimum_intersection=2)
        self.assertFalse(r["sh_600421_present_in_early_snapshot"])
        self.assertTrue(r["sh_600421_present_in_late_snapshot"])
        self.assertFalse(r["membership_delta_proves_IPO_or_delisting"])

    def test_duplicate_member_rejected_not_double_counted(self):
        rows=copy.deepcopy(EARLY)+[EARLY[0]]
        with self.assertRaisesRegex(ValueError,"Duplicated"):
            compare_rosters(rows,LATE,minimum_intersection=2)

    def test_source_board_prefix_and_status_rejected(self):
        for field,value in ((0,"sz.300750"),(1,"unknown"),(2,"")):
            rows=copy.deepcopy(EARLY)
            rows[0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,"Unknown"):
                compare_rosters(rows,LATE,minimum_intersection=2)

    def test_unreliable_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError,"overlap"):
            compare_rosters(EARLY,LATE,minimum_intersection=3)

    def test_code_digest_is_stable_not_reconstructible_member_list(self):
        r=compare_rosters(EARLY,LATE,minimum_intersection=2)
        self.assertEqual(len(r["common_code_set_sha256"]),64)
        expected=hashlib.sha256(b"sh.600000\nsh.603019\n").hexdigest()
        self.assertEqual(r["common_code_set_sha256"],expected)
        self.assertNotIn("early_only_codes",r)
        self.assertNotIn("late_only_codes",r)

    def test_status_changes_sum_to_common_issuers(self):
        e=EARLY+[["sz.000001","0","平安银行"]]
        l=LATE+[["sz.000001","0","平安银行"]]
        r=compare_rosters(e,l,minimum_intersection=2)
        self.assertEqual(sum(r["vendor_status_changes_in_common_codes"].values()),3)
        self.assertEqual(r["vendor_status_changes_in_common_codes"]["0_to_0"],1)


if __name__=="__main__":
    unittest.main()
