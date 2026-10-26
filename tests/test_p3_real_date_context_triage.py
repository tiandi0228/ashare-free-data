import unittest
from collector.p3_real_date_context_triage import classify
class TriageTests(unittest.TestCase):
    def sample(self):
        return {"phase":"P3_REAL_P1_PDF_TEXT_RESEARCH_CUES","trade_gate":"BLOCKED",
                "sources":[{"issuer":"sh.600000","announcement_id":"100","original_sha256":"a"*64,
                "historical_PIT_verified":False,"event_effective_date_certified":False,
                "date_contexts_research_only":[{"date_text":"2026年10月26日",
                "source_text_context":"自2026年10月26日起停牌，其他日期以公告为准",
                "effective_date_certified":False}]}]}
    def test_cue_does_not_prove_effectiveness(self):
        x=classify(self.sample())
        self.assertIn("TRADING_HALT_CUE",x["candidate_contexts"][0]["candidate_event_cues"])
        self.assertEqual(x["historical_issuer_states_certified"],0)
    def test_reject_fabricated_certification(self):
        x=self.sample();x["sources"][0]["date_contexts_research_only"][0]["effective_date_certified"]=True
        with self.assertRaises(ValueError):classify(x)
if __name__=="__main__":unittest.main()
