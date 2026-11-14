import copy,json,unittest
from pathlib import Path
from collector.p3_historical_st_temporal_veto import temporal_veto

M=json.loads((Path(__file__).resolve().parents[1]/
    "evidence/p3_eight_issuer_halt_resume_research_refs_20261112.json").read_text())

class STTemporalVetoTests(unittest.TestCase):
    def check(self,issuer,day,reason):
        r=temporal_veto(M,issuer,day)
        self.assertEqual(r["decision"],"BLOCK")
        self.assertEqual(r["reason"],reason)
        self.assertFalse(r["may_include_in_historical_non_ST_trade_universe"])
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_juewei_before_ST_removal_remains_excluded(self):
        self.check("sh.603517","2026-10-19",
                   "HISTORICAL_ST_BEFORE_RESEARCHED_REMOVAL_DAY")
    def test_juewei_after_removal_still_no_pit(self):
        self.check("sh.603517","2026-10-20",
                   "POST_ST_REMOVAL_DAY_STILL_NEEDS_INDEPENDENT_EXCHANGE_PIT")
    def test_sitong_before_ST_removal_remains_excluded(self):
        self.check("sh.603838","2026-10-19",
                   "HISTORICAL_ST_BEFORE_RESEARCHED_REMOVAL_DAY")
    def test_sitong_after_removal_still_no_pit(self):
        self.check("sh.603838","2026-10-20",
                   "POST_ST_REMOVAL_DAY_STILL_NEEDS_INDEPENDENT_EXCHANGE_PIT")
    def test_gac_disputed_start_14_rejected(self):
        self.check("sh.601238","2026-09-14",
                   "DISPUTED_2026_SEPTEMBER_HALT_START_NOT_EXCHANGE_VERIFIED")
    def test_gac_disputed_start_15_rejected(self):
        self.check("sh.601238","2026-09-15",
                   "DISPUTED_2026_SEPTEMBER_HALT_START_NOT_EXCHANGE_VERIFIED")
    def test_gac_resume_day_still_not_approved(self):
        self.check("sh.601238","2026-09-29",
                   "NO_INDEPENDENT_EXCHANGE_PIT_SESSION_PROOF")
    def test_other_suspension_case_also_blocked(self):
        self.check("sz.002860","2026-10-14",
                   "NO_INDEPENDENT_EXCHANGE_PIT_SESSION_PROOF")
    def test_unknown_issuer_cannot_succeed(self):
        with self.assertRaises(ValueError):
            temporal_veto(M,"sh.600000","2026-10-19")
    def test_date_not_in_iso_format_denied(self):
        with self.assertRaises(ValueError):
            temporal_veto(M,"sh.603517","2026/10/19")
    def test_untrusted_manifest_rejected(self):
        x=copy.deepcopy(M);x["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):
            temporal_veto(x,"sh.603517","2026-10-19")
    def test_empty_date_rejected(self):
        with self.assertRaises(ValueError):
            temporal_veto(M,"sh.603838","")
