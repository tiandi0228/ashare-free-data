import copy
import unittest
from collector.p3_manual_official_evidence_checklist import export

EPOCH="a"*64
VENDOR="b"*64
PDF="c"*64


def sample():
    task={
        "issuer":"sz.300100","source_epoch_sha256":EPOCH,
        "vendor_gap_diagnosis":"VENDOR_MARKED_NOT_TRADABLE_AT_ASOF",
        "original_vendor_csv_sha256":VENDOR,
        "research_action":"VERIFY_ASOF_NONTRADABLE_EXCHANGE_AND_OFFICIAL_NOTICE",
        "official_pdf_halt_resume_text_leads":1,
        "research_text_resume_pairs":0,
        "required_official_evidence":["SOURCE_AUTHENTIC_ORIGINAL_DOCUMENT_SHA",
                                        "INDEPENDENT_ASOF_EXCHANGE_TRADING_STATUS"],
        "official_evidence_authenticated":False,"historical_PIT_verified":False,
        "feature_gap_resolved":False,"buy_eligible":False}
    queue={"phase":"P2_P3_SOURCE_SHA_ISSUER_EVIDENCE_REVIEW_QUEUE",
           "status":"UNRESOLVED_OFFICIAL_PROOF_REQUIREMENTS_RESEARCH_ONLY",
           "source_epoch_sha256":EPOCH,"p2_source_run_id":123,"p3_source_run_id":456,
           "gap_issuer_count":1,"unresolved_issuer_count":1,
           "official_halt_intervals_certified":0,"feature_gaps_resolved":0,
           "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[],
           "tasks":[task]}
    notice="12345"
    path=f"pdf/sz_300100/{notice}/{PDF}.pdf"
    original={"issuer":"sz.300100","source_epoch_sha256":EPOCH,
              "vendor_csv_sha256":VENDOR,"research_action":task["research_action"],
              "original_halt_resume_text_documents":[{
                  "announcement_id":notice,"original_pdf_sha256":PDF,
                  "original_sha_verified_archive_path":path,
                  "historical_first_publication_authenticated":False,
                  "source_text_is_not_official_interval_proof":True}],
              "original_resume_research_text_pairs":[],
              "official_first_publication_verified":False,
              "complete_official_state_interval_certified":False,
              "feature_gap_resolved":False,"buy_eligible":False}
    index={"phase":"P3_GAP_ISSUER_ORIGINAL_PDF_PROVENANCE_REVIEW_INDEX",
           "status":"SHA_SOURCE_LOCATORS_ONLY_NO_FIRST_PUBLICATION_PROOF",
           "source_epoch_sha256":EPOCH,
           "p2_source_run_id":123,"p3_source_run_id":456,
           "gap_issuer_count":1,"authenticated_first_publication_count":0,
           "certified_exchange_intervals":0,"historical_PIT_verified":False,
           "trade_gate":"BLOCKED","orders":[],"issuers":[original]}
    return queue,index


class ManualOfficialReviewTests(unittest.TestCase):
    def test_independent_exchange_status_required_without_pit_promotion(self):
        q,p=sample()
        result=export(q,p)
        self.assertEqual(result["review_count"],1)
        self.assertEqual(result["asof_nontradable_tasks"],1)
        row=result["review_rows"][0]
        self.assertIn("12345:"+PDF,row["original_pdf_sha_locators"])
        self.assertIn("INDEPENDENT_ASOF_EXCHANGE_TRADING_STATUS",
                      row["missing_independent_official_proofs"])
        self.assertEqual(row["review_status"],"NOT_AUTHENTICATED")
        self.assertEqual(result["official_state_intervals_certified"],0)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertFalse(row["buy_eligible"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_forged_state_epoch_source_and_original_sha_fail_closed(self):
        for kind in ("epoch","run","missing","digest","path","certified",
                     "need","duplicates","counts","trade"):
            q,p=copy.deepcopy(sample())
            if kind=="epoch":p["source_epoch_sha256"]="d"*64
            if kind=="run":q["p3_source_run_id"]=789
            if kind=="missing":p["issuers"]=[]
            if kind=="digest":p["issuers"][0]["vendor_csv_sha256"]="d"*64
            if kind=="path":p["issuers"][0]["original_halt_resume_text_documents"][0][
                "original_sha_verified_archive_path"]="untrusted.pdf"
            if kind=="certified":p["issuers"][0]["official_first_publication_verified"]=True
            if kind=="need":q["tasks"][0]["required_official_evidence"].remove(
                "INDEPENDENT_ASOF_EXCHANGE_TRADING_STATUS")
            if kind=="duplicates":q["tasks"].append(copy.deepcopy(q["tasks"][0]))
            if kind=="counts":q["tasks"][0]["official_pdf_halt_resume_text_leads"]=0
            if kind=="trade":q["trade_gate"]="OPEN"
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                export(q,p)

if __name__=="__main__":
    unittest.main()
