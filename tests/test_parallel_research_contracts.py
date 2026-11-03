"""Four independent offline R&D lanes stay permanently research-only."""
import copy
import unittest
from collector.parallel_research_contracts import (
    rank_universe,align_quotes,pit_facts,audit_forward,
)
DAY="2026-11-03"
def ranking():
    return {"rows":[
        {"code":"600000","sector":"银行","is_st":False,"halted":False,
         "trend":"80","relative_volume":"60","sector_strength":"85","drawdown_risk":"15"},
        {"code":"002249","sector":"电机","is_st":False,"halted":False,
         "trend":"60","relative_volume":"40","sector_strength":"55","drawdown_risk":"30"}]}
def quotes():
    return {"checked_at":DAY+"T10:30:12+08:00","quotes":[
        {"code":"002249","source":"tencent","quote_time":DAY+"T10:30:06+08:00","price":"10.00"},
        {"code":"002249","source":"independent","quote_time":DAY+"T10:30:08+08:00","price":"10.01"}]}
def pit():
    return {"decision_at":DAY+"T10:30:00+08:00","facts":[
        {"code":"002249","kind":k,"published_at":"2026-11-02T16:00:00+08:00",
         "available_at":"2026-11-02T17:00:00+08:00",
         "effective_from":"2026-11-02T00:00:00+08:00",
         "original_sha256":"a"*64,"original_durably_archived":True}
        for k in ("listing","st","halt","corporate_action")]}
def forward():
    return {"records":[{"id":"frozen_1",
        "frozen_at":DAY+"T10:29:00+08:00","decision_at":DAY+"T10:30:00+08:00",
        "observed_at":"2026-11-04T15:00:00+08:00","outcome":"NO_FILL",
        "original_signal_sha256":"b"*64,"trade_gate":"BLOCKED","orders":[]}]}

class ResearchContractsTests(unittest.TestCase):
    def test_rank_full_research_only_and_deterministic(self):
        r=rank_universe(ranking())
        self.assertEqual(r["status"],"RESEARCH_RANKING_NOT_ACTIONABLE")
        self.assertEqual([x["code"] for x in r["research_ranking"]],
                         ["600000","002249"])
        self.assertEqual(r["actionable_buy_signals"],[])
        self.assertEqual(r["orders"],[])
        self.assertFalse(r["certified"])
    def test_rank_rejects_chinext_st_bad_values_or_duplicate(self):
        for mutation in ("300015","st","nan","duplicate"):
            p=ranking()
            if mutation=="300015":p["rows"][0]["code"]="300015"
            if mutation=="st":p["rows"][0]["is_st"]=None
            if mutation=="nan":p["rows"][0]["trend"]="NaN"
            if mutation=="duplicate":p["rows"][1]["code"]="600000"
            with self.subTest(mutation=mutation):
                self.assertEqual(rank_universe(p)["status"],"REJECTED")
        self.assertEqual(rank_universe({"rows":[]})["status"],"REJECTED")
    def test_two_quote_time_alignment_still_not_certified(self):
        r=align_quotes(quotes())
        self.assertEqual(r["status"],"TIME_ALIGNED_QUOTE_CANDIDATE_NOT_CERTIFIED")
        self.assertTrue(r["quote_freshness_structural_check"])
        self.assertFalse(r["certified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_quotes_stale_mismatch_and_same_source_reject(self):
        for kind in ("stale","skew","price","same_source","future"):
            p=quotes()
            if kind=="stale":p["quotes"][0]["quote_time"]=DAY+"T10:29:40+08:00"
            if kind=="skew":p["quotes"][1]["quote_time"]=DAY+"T10:30:12+08:00"
            if kind=="price":p["quotes"][1]["price"]="10.50"
            if kind=="same_source":p["quotes"][1]["source"]="tencent"
            if kind=="future":p["quotes"][1]["quote_time"]=DAY+"T10:30:20+08:00"
            with self.subTest(kind=kind):
                self.assertEqual(align_quotes(p)["status"],"REJECTED")
                self.assertEqual(align_quotes(p)["orders"],[])
    def test_pit_complete_structure_never_certifies(self):
        r=pit_facts(pit())
        self.assertEqual(r["status"],"STRUCTURAL_PIT_COVERAGE_NOT_AUTHENTICATED")
        self.assertFalse(r["certified"])
        self.assertEqual(r["covered_symbols"],1)
    def test_pit_future_missing_and_duplicate_reject(self):
        p=pit();p["facts"][0]["available_at"]="2026-11-04T12:00:00+08:00"
        self.assertEqual(pit_facts(p)["status"],"REJECTED")
        p=pit();p["facts"].pop()
        self.assertEqual(pit_facts(p)["status"],"REJECTED")
        p=pit();p["facts"].append(copy.deepcopy(p["facts"][0]))
        self.assertEqual(pit_facts(p)["status"],"REJECTED")
        p=pit();p["facts"][0]["original_sha256"]="unknown"
        self.assertEqual(pit_facts(p)["status"],"REJECTED")
    def test_forward_observations_have_frozen_past_and_future_result(self):
        r=audit_forward(forward())
        self.assertEqual(r["status"],"FORWARD_OBSERVATION_STRUCTURE_ONLY")
        self.assertEqual(r["outcome_counts"]["NO_FILL"],1)
        self.assertFalse(r["certified"])
    def test_forward_lookahead_duplicate_or_open_gate_rejected(self):
        for kind in ("lookahead","frozen_late","duplicate","open_gate","fake_fill"):
            p=forward()
            row=p["records"][0]
            if kind=="lookahead":row["observed_at"]=DAY+"T10:20:00+08:00"
            if kind=="frozen_late":row["frozen_at"]=DAY+"T10:31:00+08:00"
            if kind=="duplicate":p["records"].append(copy.deepcopy(row))
            if kind=="open_gate":row["trade_gate"]="OPEN"
            if kind=="fake_fill":row["orders"]=[{"side":"BUY"}]
            with self.subTest(kind=kind):
                r=audit_forward(p)
                self.assertEqual(r["status"],"REJECTED")
                self.assertEqual(r["orders"],[])
                self.assertEqual(r["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
