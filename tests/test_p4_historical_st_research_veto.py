"""Historical ST non-ST policy fail-closed research unit regressions."""
import copy
import unittest
from collector.p4_historical_st_research_veto import classify
from collector.p3_four_issuer_st_crosswalk import reconcile
from tests.test_p3_four_issuer_st_crosswalk import inputs

def context():
    gap, sources=inputs()
    crosswalk=reconcile(gap,sources)
    rows=[
      {"issuer":"sh.600363","signal_known_after_close_date":"2026-09-28","research_only":True,"buy_signal":False},
      {"issuer":"sh.600363","signal_known_after_close_date":"2026-09-29","research_only":True,"buy_signal":False},
      {"issuer":"sh.600363","signal_known_after_close_date":"2026-09-30","research_only":True,"buy_signal":False},
      {"issuer":"sh.600363","signal_known_after_close_date":"2026-10-20","research_only":True,"buy_signal":False},
      {"issuer":"sh.600825","signal_known_after_close_date":"2026-09-30","research_only":True,"buy_signal":False},
    ]
    return crosswalk,rows

class HistoricalSTRiskTests(unittest.TestCase):
    def setUp(self):
        self.crosswalk,self.rows=context()

    def must_reject(self):
        with self.assertRaises(ValueError):
            classify(self.crosswalk,self.rows)

    def test_pre_halt_halt_and_st_states(self):
        r=classify(self.crosswalk,self.rows)
        self.assertEqual([x["candidate_policy_research_state"] for x in r["research_decisions"]],[
            "PRE_ST_NOTICE_INTERVAL_NOT_PIT_AUTHENTICATED",
            "VETO_ISSUER_NOTICE_SUSPENDED_DAY",
            "VETO_ISSUER_NOTICE_ST_EFFECTIVE",
            "VETO_ISSUER_NOTICE_ST_EFFECTIVE",
            "UNKNOWN_PIT_STATUS_FAIL_CLOSED",
        ])
        self.assertEqual(r["approved_entries"],0)
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["executable_candidates"],[])
        self.assertFalse(r["historical_PIT_verified"])
        self.assertFalse(r["production_trade_gate_implementation_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_different_issuer_never_inherits_600363_st(self):
        r=classify(self.crosswalk,self.rows)
        self.assertEqual(r["research_decisions"][-1]["candidate_policy_research_state"],
                         "UNKNOWN_PIT_STATUS_FAIL_CLOSED")

    def test_st_change_date_altered(self):
        self.crosswalk["st_risk_exclusion"]["effective_from"]="2026-10-01"
        self.must_reject()

    def test_st_issuer_pit_forgery(self):
        self.crosswalk["historical_PIT_verified"]=True
        self.must_reject()

    def test_st_notice_date_drift(self):
        self.crosswalk["issuer_results"]["sh.600363"]["curated_issuer_halt_start"]="2026-09-28"
        self.must_reject()

    def test_source_sha_not_claimed_authentic(self):
        self.crosswalk["issuer_results"]["sh.600363"]["source_pdf_bytes_sha_verified"]=True
        self.must_reject()

    def test_unsupported_issuer(self):
        self.rows[0]["issuer"]="sh.688001"
        self.must_reject()

    def test_duplicate_symbol_date(self):
        self.rows.append(copy.deepcopy(self.rows[1]))
        self.must_reject()

    def test_cannot_be_trade_signal(self):
        self.rows[2]["buy_signal"]=True
        self.must_reject()

    def test_cannot_launder_nonresearch_candidate(self):
        self.rows[2]["research_only"]=False
        self.must_reject()

    def test_bad_date(self):
        self.rows[2]["signal_known_after_close_date"]="2026-09-31"
        self.must_reject()

    def test_weekend_no_signal(self):
        self.rows[2]["signal_known_after_close_date"]="2026-10-03"
        self.must_reject()

    def test_cannot_open_trade_gate(self):
        self.crosswalk["trade_gate"]="OPEN"
        self.must_reject()
