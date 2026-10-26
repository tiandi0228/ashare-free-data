import unittest
from collector.p3_real_context_decision_join import join
class Tests(unittest.TestCase):
 def test_match_is_research_only(self):
  w={"phase":"P3_P1_OBSERVED_WORKLIST","trade_gate":"BLOCKED","official_evidence_cells_required":1,
     "official_evidence_tasks":[{"code":"sh.600000","decision_date":"2026-10-20","kind":"halt"}]}
  t={"phase":"P3_REAL_P1_DATE_CONTEXT_TRIAGE","trade_gate":"BLOCKED","candidate_contexts":[{"issuer":"sh.600000","announcement_id":"100","original_sha256":"a"*64,"date_text":"2026年10月20日","candidate_event_cues":["TRADING_HALT_CUE"],"historical_effective_date_verified":False,"historical_publication_time_verified":False}]}
  q=join(w,t)
  self.assertEqual(q["research_lead_links"],1)
  self.assertEqual(q["official_pit_certified_cells"],0)
  self.assertFalse(q["research_only_links"][0]["evidence_usable_asof_decision"])
if __name__=="__main__":unittest.main()
