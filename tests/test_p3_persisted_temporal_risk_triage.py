import unittest
from collector.p3_persisted_temporal_risk_triage import audit

def manifest():
    rows=[]
    for issuer,day,event,claim,excerpt in [
        ("sh.600302","2026-04-30","HALT_START","2026年4月30日","公司股票于2026年4月30日停牌一日"),
        ("sh.600303","2025-04-18","HALT_START","2025年4月18日","公司股票将于2025年4月18日停牌一天"),
        ("sh.600303","2025-04-18","ST_REMOVED","2025年4月17日","上海证券交易所于2025年4月17日同意公司撤销其他风险警示"),
        ("sh.600319","2025-11-04","HALT_START","2025年11月4日","公司股票自2025年11月4日开市起停牌"),
        ("sh.600319","2025-11-17","HALT_START","2025年11月4日","公司股票自2025年11月4日开市起停牌"),
    ]:
        rows.append({"issuer":issuer,"announcement_id":"1222222222",
            "decision_day":day,"source_date_text":claim,
            "local_textual_direction_candidate":event,"source_clause_excerpt":excerpt,
            "original_pdf_sha256":"a"*64,
            "index_time_screen":"INDEX_TIME_NOT_AFTER_DECISION_CLOSE_UNVERIFIED",
            "effective_date_authenticated":False,"first_publication_authenticated":False,
            "decision_time_available_certified":False})
    return {"phase":"P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE",
        "run_id":42,"trade_gate":"BLOCKED","orders":[],
        "historical_PIT_verified":False,"certified_first_publication_count":0,
        "certified_event_effective_day_count":0,"certified_historical_decision_state_count":0,
        "explicit_local_textual_candidate_count":5,"research_date_action_links":rows}

class TemporalRiskTests(unittest.TestCase):
    def test_actual_five_candidate_pattern(self):
        result=audit(manifest())
        self.assertEqual(result["explicit_textual_candidate_count"],5)
        self.assertEqual(result["candidate_with_text_date_not_decision_day"],2)
        self.assertEqual(result["candidate_with_approval_not_effective_date"],1)
        self.assertEqual(result["certified_event_effective_dates"],0)
        self.assertFalse(result["historical_PIT_verified"])
    def test_forged_PIT_blocks(self):
        data=manifest()
        data["research_date_action_links"][0]["decision_time_available_certified"]=True
        with self.assertRaises(ValueError):audit(data)
    def test_index_time_after_decision_blocks_any_inference(self):
        data=manifest();data["research_date_action_links"][0]["index_time_screen"]="INDEX_TIME_AFTER_DECISION_CLOSE_UNVERIFIED"
        flags=audit(data)["original_sha_linked_manual_review"][0]["research_cautions"]
        self.assertIn("INDEX_METADATA_AFTER_DECISION_CLOSE",flags)
    def test_promotion_of_unverified_index_time_rejected(self):
        data=manifest();data["research_date_action_links"][0]["index_time_screen"]="AUTHENTICATED"
        with self.assertRaises(ValueError):audit(data)
    def test_mismatched_text_excerpt_not_accepted(self):
        data=manifest();data["research_date_action_links"][0]["source_clause_excerpt"]="公司股票停牌"
        with self.assertRaises(ValueError):audit(data)
    def test_invalid_calendar_date_rejected(self):
        data=manifest()
        data["research_date_action_links"][0]["source_date_text"]="2026年2月30日"
        data["research_date_action_links"][0]["source_clause_excerpt"]="于2026年2月30日停牌"
        with self.assertRaises(ValueError):audit(data)
if __name__=="__main__":unittest.main()
