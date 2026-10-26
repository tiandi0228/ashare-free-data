import unittest
from collector.p3_original_effective_clause_review import classify,review
from tests.test_p3_full_queue_scout import fixture
from collector.p3_full_queue_source_join import reconcile

def sample(context="公司股票自2026年10月20日起停牌。",issuer_in_text=True):
    args=fixture()
    args[5]["candidate_contexts"][0]["source_text_context"]=context
    joined=reconcile(*args)
    issuer=args[1]["targets"][0]["issuer"]
    pdf={"phase":"P3_REAL_P1_PDF_TEXT_RESEARCH_CUES","trade_gate":"BLOCKED",
         "orders":[],"historical_PIT_verified":False,
         "sources":[{"issuer":issuer,"announcement_id":"123",
                     "original_sha256":"c"*64,"historical_PIT_verified":False,
                     "issuer_code_in_text":issuer_in_text}]}
    args[3]["sources"][0]["observed_at_utc"]="2026-10-26T11:00:00+00:00"
    args[2]["results"][0]["candidates"]=[
        {"announcement_id":"123","index_published_milliseconds_unverified":1792252800000}]
    return joined,args[5],pdf,args[3],args[2]

class TestOriginalClauseReview(unittest.TestCase):
    def test_explicit_halt_clause_not_pit(self):
        r=review(*sample())
        self.assertEqual(r["explicit_original_clause_candidates"],1)
        item=r["manual_review_only"][0]
        self.assertEqual(item["local_textual_direction_candidate"],"HALT_START")
        self.assertFalse(item["historical_asof_usable"])
        self.assertEqual(r["official_PIT_cells_certified"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_unrelated_date_and_action_same_document_not_explicit(self):
        r=review(*sample("2026年10月20日为董事会会议日期。公司股票将停牌。"))
        self.assertEqual(r["explicit_original_clause_candidates"],0)
    def test_no_issuer_code_blocks_clausal_promotion(self):
        r=review(*sample(issuer_in_text=False))
        self.assertEqual(r["explicit_original_clause_candidates"],0)
        self.assertEqual(r["issuer_code_missing_links"],1)
    def test_forecast_not_effective(self):
        r=review(*sample("公司股票预计自2026年10月20日起停牌。"))
        self.assertEqual(r["explicit_original_clause_candidates"],0)
    def test_missing_pdf_sha_rejected(self):
        args=list(sample())
        args[2]["sources"][0]["original_sha256"]="d"*64
        with self.assertRaises(ValueError):review(*args)
    def test_local_multi_dates_ambiguous(self):
        x=classify("公司自2026年10月19日至2026年10月20日停牌","2026年10月20日","halt")
        self.assertIsNone(x["local_textual_direction_candidate"])
    def test_direction_resumption(self):
        x=classify("股票将于2026年10月20日开市起复牌。","2026年10月20日","halt")
        self.assertEqual(x["local_textual_direction_candidate"],"RESUME_START")
    def test_same_clause_but_without_causal_prefix_not_effective(self):
        x=classify("2026年10月20日经营情况涉及停牌事项。","2026年10月20日","halt")
        self.assertIsNone(x["local_textual_direction_candidate"])
    def test_upstream_claimed_pit_is_rejected(self):
        args=list(sample());args[0]["official_PIT_cells_certified"]=1
        with self.assertRaises(ValueError):review(*args)
    def test_wrong_date_context_rejected(self):
        args=list(sample());args[1]["candidate_contexts"][0]["source_text_context"]="公司股票自2026年10月21日起停牌。"
        with self.assertRaises(ValueError):review(*args)

if __name__=="__main__":unittest.main()
