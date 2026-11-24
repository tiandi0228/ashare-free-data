import copy
import unittest
from collector.p3_official_source_candidate_intake import intake
from tests.test_p3_manual_official_evidence_checklist import sample
from collector.p3_manual_official_evidence_checklist import export


def fixture():
    checklist=export(*sample())
    return checklist


def candidate():
    return {
        "issuer":"sz.300100",
        "kind":"ASOF_EXCHANGE_TRADING_STATE",
        "vendor_original_csv_sha256":"b"*64,
        "original_document_sha256":"c"*64,
        "official_source_url":"https://www.szse.cn/disclosure/notice.html",
        "claimed_first_publication_at":"2026-10-19T16:00:00+08:00",
        "claimed_effective_day":"2026-10-20",
        "original_archived_at":"2026-11-24T02:00:00Z",
        "claimed_exchange_state":"HALTED",
    }


class OfficialCandidateIntakeTests(unittest.TestCase):
    def test_missing_independent_sources_are_not_promoted(self):
        result=intake(fixture(),[])
        self.assertEqual(result["issuers_in_scope"],1)
        self.assertEqual(result["asof_nontradable_issuers"],1)
        self.assertEqual(result["candidate_citations_received"],0)
        self.assertEqual(result["authenticated_first_publication_count"],0)
        self.assertEqual(result["certified_exchange_intervals"],0)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["buy_signals"],[])

    def test_even_well_formed_official_citation_is_not_authenticated(self):
        result=intake(fixture(),[candidate()])
        self.assertEqual(result["candidate_citations_received"],1)
        self.assertEqual(result["issuers_with_candidate_citations"],1)
        review=result["review_items"][0]
        source=review["candidate_citations"][0]
        self.assertEqual(source["claimed_exchange_state"],"HALTED")
        self.assertEqual(source["claimed_first_publication_at"],"2026-10-19T08:00:00+00:00")
        self.assertFalse(source["authenticated_publication"])
        self.assertFalse(source["authenticated_exchange_effective_date"])
        self.assertTrue(review["remaining_independent_authentications_required"])
        self.assertFalse(review["buy_eligible"])
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_forged_or_unsafe_candidate_fails_closed(self):
        invalid=[
            ("issuer","sh.600001"),
            ("kind","MA20_CROSS"),
            ("vendor_original_csv_sha256","d"*64),
            ("original_document_sha256","bad"),
            ("official_source_url","https://www.szse.cn.evil.test/notice"),
            ("official_source_url","http://www.szse.cn/notice"),
            ("official_source_url","https://user@www.szse.cn/notice"),
            ("official_source_url","https://www.szse.cn:444/notice"),
            ("official_source_url","https://www.szse.cn/notice#fragment"),
            ("claimed_first_publication_at","2026-10-19T16:00:00"),
            ("claimed_first_publication_at","2026-11-25T16:00:00+08:00"),
            ("claimed_effective_day","2026-02-30"),
            ("claimed_exchange_state","BUY_NOW"),
        ]
        for key,value in invalid:
            with self.subTest(key=key,value=value):
                entry=candidate()
                entry[key]=value
                with self.assertRaises(ValueError):
                    intake(fixture(),[entry])

    def test_duplicate_and_unauthenticated_checklist_forgery_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            intake(fixture(),[candidate(),candidate()])
        for key,value in (
            ("trade_gate","OPEN"),
            ("historical_PIT_verified",True),
            ("official_first_publication_authenticated",1),
            ("review_count",2),
            ("asof_nontradable_tasks",0),
        ):
            source=fixture()
            source[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                intake(source,[])
        source=fixture()
        source["review_rows"][0]["review_status"]="AUTHENTICATED"
        with self.assertRaises(ValueError):
            intake(source,[])

if __name__=="__main__":
    unittest.main()
