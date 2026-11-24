import copy
import hashlib
import unittest
from collector.p3_asof_original_notice_review_packets import build

SHA="a"*64
EPOCH="b"*64
ISSUER="sz.002388"

def fixture():
    text1="公司自2026年10月20日起停牌。"
    text2="公司拟于2026年10月21日起停牌。"
    contexts=[(text1,["HALT_START"],"SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW"),
              (text2,[],"DATE_CONTEXT_WITHOUT_EXPLICIT_EVENT")]
    leads=[];triage=[]
    for i,(phrase,directions,classification) in enumerate(contexts):
        day="2026年10月20日" if i==0 else "2026年10月21日"
        fp=hashlib.sha256(phrase.encode()).hexdigest()
        leads.append({
            "issuer":ISSUER,"announcement_id":"123","original_pdf_sha256":SHA,
            "original_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-10-20/123.PDF",
            "source_date_text":day,"source_context_sha256":fp,
            "candidate_event_directions":directions,"research_classification":classification,
            "text_is_not_official_first_publication_proof":True,
            "historical_first_publication_authenticated":False,
            "official_effective_interval_certified":False,
            "historical_trade_eligible":False})
        triage.append({
            "issuer":ISSUER,"announcement_id":"123","original_sha256":SHA,
            "date_text":day,"source_text_context":phrase,
            "human_review_required":True,
            "historical_effective_date_verified":False,
            "historical_publication_time_verified":False})
    cw={"phase":"P3_THREE_ASOF_ORIGINAL_NOTICE_DATE_LEAD_CROSSWALK",
        "status":"SHA_BOUND_DATE_TEXT_LEADS_NOT_OFFICIAL_EVENTS",
        "source_epoch_sha256":EPOCH,"research_issuers":3,"date_context_leads":2,
        "classification_counts":{"SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW":1,
                                 "DATE_CONTEXT_WITHOUT_EXPLICIT_EVENT":1},
        "first_publication_times_independently_authenticated":0,
        "official_state_intervals_certified":0,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"leads":leads}
    tri={"phase":"P3_REAL_P1_DATE_CONTEXT_TRIAGE",
         "trade_gate":"BLOCKED","historical_PIT_verified":False,
         "historical_issuer_states_certified":0,
         "orders":[],"research_date_context_count":2,"candidate_contexts":triage}
    return cw,tri

class ReviewPacketsTests(unittest.TestCase):
    def test_exact_sha_clause_review_preserves_uncertified_states(self):
        result=build(*fixture())
        self.assertEqual(result["total_contexts"],2)
        self.assertEqual(result["priority_event_candidates"],1)
        self.assertEqual(result["other_quarantined"],1)
        row=result["review_queue"][0]
        self.assertEqual(row["source_clause_excerpt"],"公司自2026年10月20日起停牌。")
        self.assertEqual(row["event_direction_candidates"],"HALT_START")
        self.assertEqual(row["review_status"],"NOT_AUTHENTICATED")
        self.assertFalse(row["buy_eligible"])
        self.assertEqual(result["official_first_publication_authenticated"],0)
        self.assertEqual(result["official_state_intervals_certified"],0)
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_repeated_identical_context_collapses_without_event_promotion(self):
        cw,tri=fixture()
        tri["candidate_contexts"].append(copy.deepcopy(tri["candidate_contexts"][0]))
        tri["research_date_context_count"]=3
        cw["duplicate_source_text_contexts_collapsed"]=1
        result=build(cw,tri)
        self.assertEqual(result["total_contexts"],2)
        self.assertEqual(result["priority_event_candidates"],1)
        self.assertEqual(result["official_state_intervals_certified"],0)
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_sha_mismatch_forged_claims_and_duplicates_rejected(self):
        for case in ("sha","clause","issuer","direction","classification",
                     "certification","duplicate","triage_duplicate","count",
                     "gate","first_pub"):
            cw,tri=copy.deepcopy(fixture())
            if case=="sha":cw["leads"][0]["source_context_sha256"]="f"*64
            elif case=="clause":tri["candidate_contexts"][0]["source_text_context"]="错假的日期2026年10月20日"
            elif case=="issuer":tri["candidate_contexts"][0]["issuer"]="sz.002717"
            elif case=="direction":cw["leads"][0]["candidate_event_directions"]=[]
            elif case=="classification":cw["leads"][1]["research_classification"]="SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW"
            elif case=="certification":cw["leads"][0]["historical_trade_eligible"]=True
            elif case=="duplicate":
                cw["leads"].append(copy.deepcopy(cw["leads"][0]))
                cw["date_context_leads"]=3
            elif case=="triage_duplicate":
                tri["candidate_contexts"].append(copy.deepcopy(tri["candidate_contexts"][0]))
                tri["research_date_context_count"]=3
            elif case=="count":cw["classification_counts"]["SAME_CLAUSE_TEXT_CANDIDATE_MANUAL_REVIEW"]=2
            elif case=="gate":tri["trade_gate"]="OPEN"
            elif case=="first_pub":cw["first_publication_times_independently_authenticated"]=1
            with self.subTest(case=case),self.assertRaises(ValueError):
                build(cw,tri)

if __name__=="__main__":unittest.main()
