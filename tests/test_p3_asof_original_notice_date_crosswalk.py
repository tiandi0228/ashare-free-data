import copy
import unittest
from collector.p3_asof_original_notice_date_crosswalk import join

EPOCH="a"*64
DIGEST="b"*64
URL="https://static.cninfo.com.cn/finalpage/2026-10-20/12345.PDF"


def fixtures():
    issuers=["sz.002388","sz.002717","sz.002731"]
    discovery={"phase":"P3_THREE_ASOF_VENDOR_GAP_OFFICIAL_INDEX_RESEARCH",
               "source_epoch_sha256":EPOCH,
               "research_issuers":3,"trade_gate":"BLOCKED",
               "historical_PIT_verified":False,"orders":[],
               "results":[{"issuer":issuer,"official_asof_state_authenticated":False,
                   "independent_exchange_status_authenticated":False,
                   "candidates":[{"announcement_id":str(12345+i),
                       "official_pdf_url":URL.replace("12345",str(12345+i)),
                       "index_published_milliseconds_unverified":1792454400000,
                       "historical_PIT_verified":False,
                       "original_bytes_captured":False}]} for i,issuer in enumerate(issuers)]}
    receipt={"phase":"P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE",
             "trade_gate":"BLOCKED","historical_PIT_verified":False,
             "orders":[],"attempted":1,"retrieved":1,"sources":[{
                 "issuer":issuers[0],"announcement_id":"12345","sha256":DIGEST,
                 "url":URL,"original_bytes_verified":True,
                 "historical_first_publication_authenticated":False,
                 "historical_PIT_verified":False}]}
    pdf={"phase":"P3_REAL_P1_PDF_TEXT_RESEARCH_CUES",
         "trade_gate":"BLOCKED","historical_PIT_verified":False,"orders":[],
         "source_count":1,"sources":[{"issuer":issuers[0],
             "announcement_id":"12345","original_sha256":DIGEST,
             "text_status":"TEXT_EXTRACTED_RESEARCH_ONLY",
             "historical_PIT_verified":False}]}
    triage={"phase":"P3_REAL_P1_DATE_CONTEXT_TRIAGE",
            "trade_gate":"BLOCKED","historical_PIT_verified":False,"orders":[],
            "research_date_context_count":1,
            "candidate_contexts":[{
                "issuer":issuers[0],"announcement_id":"12345",
                "original_sha256":DIGEST,"date_text":"2026年10月20日",
                "source_text_context":"公司自2026年10月20日起停牌。",
                "historical_publication_time_verified":False,
                "historical_effective_date_verified":False,
                "human_review_required":True}]}
    return discovery,receipt,pdf,triage


class AsofOriginalNoticeDateCrosswalkTests(unittest.TestCase):
    def test_original_sha_bound_clause_not_official_certification(self):
        report=join(*fixtures())
        self.assertEqual(report["research_issuers"],3)
        self.assertEqual(report["sha_verified_original_pdfs"],1)
        self.assertEqual(report["date_context_leads"],1)
        lead=report["leads"][0]
        self.assertEqual(lead["candidate_event_directions"],["HALT_START"])
        self.assertEqual(lead["original_pdf_sha256"],DIGEST)
        self.assertEqual(lead["announcement_id"],"12345")
        self.assertEqual(lead["research_classification"],
                         "SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW")
        self.assertFalse(lead["historical_first_publication_authenticated"])
        self.assertFalse(lead["official_effective_interval_certified"])
        self.assertEqual(report["official_state_intervals_certified"],0)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])

    def test_repeated_identical_date_context_is_one_source_not_two_proofs(self):
        d,r,p,t=fixtures()
        t["candidate_contexts"].append(copy.deepcopy(t["candidate_contexts"][0]))
        t["research_date_context_count"]=2
        report=join(d,r,p,t)
        self.assertEqual(report["date_context_leads"],1)
        self.assertEqual(report["duplicate_source_text_contexts_collapsed"],1)
        self.assertEqual(report["official_state_intervals_certified"],0)
        self.assertEqual(report["trade_gate"],"BLOCKED")

    def test_nonaffirmative_clause_not_promoted(self):
        d,r,p,t=fixtures()
        t["candidate_contexts"][0]["source_text_context"]="公司拟于2026年10月20日起停牌。"
        report=join(d,r,p,t)
        self.assertEqual(report["leads"][0]["candidate_event_directions"],[])
        self.assertFalse(report["leads"][0]["historical_trade_eligible"])

    def test_forged_or_unbound_original_rejected(self):
        for kind in ("issuer","digest","notice","url","publication","effective",
                     "duplicate","source","count","trade"):
            d,r,p,t=copy.deepcopy(fixtures())
            if kind=="issuer":t["candidate_contexts"][0]["issuer"]="sz.002860"
            elif kind=="digest":t["candidate_contexts"][0]["original_sha256"]="c"*64
            elif kind=="notice":t["candidate_contexts"][0]["announcement_id"]="666"
            elif kind=="url":r["sources"][0]["url"]="https://fake.example/PDF"
            elif kind=="publication":t["candidate_contexts"][0]["historical_publication_time_verified"]=True
            elif kind=="effective":t["candidate_contexts"][0]["historical_effective_date_verified"]=True
            elif kind=="duplicate":
                t["candidate_contexts"].append(copy.deepcopy(t["candidate_contexts"][0]))
                t["research_date_context_count"]=2
            elif kind=="source":p["sources"][0]["original_sha256"]="d"*64
            elif kind=="count":r["retrieved"]=0
            elif kind=="trade":d["trade_gate"]="OPEN"
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                join(d,r,p,t)

if __name__=="__main__":
    unittest.main()
