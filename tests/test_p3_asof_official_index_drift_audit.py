import copy
import unittest
from collector.p3_asof_official_index_drift_audit import compare
from tests.test_p3_asof_index_research_continuity import source,CODES

RUN=45319344709

class OfficialIndexDriftAuditTests(unittest.TestCase):
    def test_same_notice_stability_never_certifies_publication(self):
        result=compare(source(),source(),RUN)
        self.assertEqual(result["issuers_in_scope"],3)
        self.assertEqual(result["comparison_rows"],3)
        self.assertEqual(result["comparison_class_counts"],{
            "SAME_NOTICE_INDEX_METADATA_STABLE_NOT_PUBLICATION_PROOF":3})
        self.assertEqual(result["authenticated_first_publication_count"],0)
        self.assertEqual(result["certified_exchange_intervals"],0)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_changed_timestamp_and_url_are_review_flags(self):
        current,prior=source(),source()
        current["results"][0]["candidates"][0]["index_published_milliseconds_unverified"]=1792540800000
        current["results"][1]["candidates"][0]["official_pdf_url"]=( 
            "https://static.cninfo.com.cn/finalpage/2026-10-21/12346.PDF")
        result=compare(current,prior,RUN)
        self.assertEqual(result["comparison_class_counts"][
            "SAME_NOTICE_INDEX_TIME_CHANGED_REVIEW_REQUIRED"],1)
        self.assertEqual(result["comparison_class_counts"][
            "SAME_NOTICE_PDF_URL_CHANGED_REVIEW_REQUIRED"],1)
        self.assertFalse(any(r["authenticated_first_publication"] for r in result["rows"]))

    def test_current_absence_is_not_notice_deletion(self):
        now,prior=source(),source()
        now["results"][0]["candidates"].append({
            "announcement_id":"99999",
            "official_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-10-20/99999.PDF",
            "historical_PIT_verified":False,"original_bytes_captured":False})
        now["index_candidates"]=4
        report=compare(now,prior,RUN)
        self.assertEqual(report["comparison_class_counts"][
            "CURRENT_ONLY_INDEX_MATCH_NOT_NEW_PUBLICATION_PROOF"],1)
        self.assertEqual(report["trade_gate"],"BLOCKED")

    def test_unavailable_index_cannot_be_claimed_stable(self):
        report=compare(source([CODES[0]]),source(),RUN)
        self.assertEqual(report["comparison_class_counts"][
            "CURRENT_INDEX_UNAVAILABLE_NO_COMPARISON"],1)
        self.assertEqual(report["comparison_rows"],3)
        self.assertEqual(report["authenticated_first_publication_count"],0)

    def test_source_sha_and_claim_forgeries_fail_closed(self):
        for kind in ("epoch","sha","window","false_pit","bad_url",
                     "duplicate","count","gate","run"):
            current,prior=copy.deepcopy((source(),source()))
            run=RUN
            if kind=="epoch":prior["source_epoch_sha256"]="b"*64
            elif kind=="sha":prior["results"][0]["original_vendor_csv_sha256"]="f"*64
            elif kind=="window":prior["results"][0]["research_window_end"]="2026-10-26"
            elif kind=="false_pit":prior["results"][0]["candidates"][0]["historical_PIT_verified"]=True
            elif kind=="bad_url":current["results"][0]["candidates"][0]["official_pdf_url"]="https://evil.example/file.pdf"
            elif kind=="duplicate":current["results"][1]["issuer"]=current["results"][0]["issuer"]
            elif kind=="count":current["index_candidates"]=88
            elif kind=="gate":prior["trade_gate"]="OPEN"
            elif kind=="run":run=0
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                compare(current,prior,run)

if __name__=="__main__":
    unittest.main()
