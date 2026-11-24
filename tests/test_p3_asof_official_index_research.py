import copy
import unittest
from collector.p3_asof_official_index_research import targets,discover

EPOCH="a"*64


def fixture():
    all_codes=["sh.600293","sh.600301","sh.600363","sz.002717","sz.002870"]
    rows=[]
    for i,code in enumerate(all_codes):
        asof=i<3
        rows.append({"issuer":code,
            "original_csv_sha256":f"{i+1:064x}",
            "asof_date":"2026-10-20",
            "diagnosis":("VENDOR_MARKED_NOT_TRADABLE_AT_ASOF" if asof else
                         "VENDOR_SUSPENDED_ROW_WITHIN_LAST_21"),
            "trailing_vendor_suspended_rows":1,
            "official_halt_explanation_authenticated":False})
    coverage={
        "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
        "source_epoch_sha256":EPOCH,"trade_gate":"BLOCKED",
        "historical_PIT_verified":False,"orders":[],
        "observed_archived_shards":400,"checkpoint_completed_shards":400,
        "unobserved_archived_shards":0,
        "gap_issuer_codes":all_codes,"issuer_evidence_gap_count":5,
        "gap_reason_counts":{"VENDOR_NOT_TRADABLE_ASOF":3,
                             "INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS":2}}
    gaps={"phase":"P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS",
          "status":"SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY",
          "source_epoch_sha256":EPOCH,"trade_gate":"BLOCKED",
          "historical_PIT_verified":False,"coverage_gaps_resolved":0,
          "orders":[],"research_gap_issuers":5,"results":rows}
    return coverage,gaps


class AsofIndexResearchTests(unittest.TestCase):
    def test_selection_uses_original_SHA_and_frozen_window(self):
        rows=targets(*fixture())
        self.assertEqual(len(rows),3)
        self.assertEqual([r["issuer"] for r in rows],
                         ["sh.600293","sh.600301","sh.600363"])
        self.assertEqual(rows[0]["research_window_start"],"2026-09-05")
        self.assertEqual(rows[0]["research_window_end"],"2026-10-27")
        self.assertFalse(rows[0]["official_asof_state_authenticated"])

    def test_success_empty_and_unavailable_are_research_only(self):
        def client(issuer,research_window=None):
            self.assertEqual(research_window,["2026-09-05","2026-10-27"])
            if issuer=="sh.600293":
                return [{"historical_PIT_verified":False,
                         "original_bytes_captured":False,
                         "announcement_id":"123"}]
            if issuer=="sh.600301":
                return []
            raise TimeoutError("provider not reachable")
        report=discover(*fixture(),client=client)
        self.assertEqual(report["research_issuers"],3)
        self.assertEqual(report["index_candidates"],1)
        self.assertEqual(report["index_unavailable"],1)
        self.assertEqual(report["transient_retry_issuers"],1)
        self.assertEqual(report["total_index_query_attempts"],4)
        self.assertEqual(report["no_index_match_not_no_risk"],1)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])
        self.assertFalse(report["independent_exchange_status_authenticated"])
        self.assertFalse(report["historical_PIT_verified"])

    def test_bounded_transport_retry_and_no_retry_of_unsafe_source(self):
        from urllib.error import HTTPError
        attempts={}
        def client(issuer,research_window=None):
            attempts[issuer]=attempts.get(issuer,0)+1
            if issuer=="sh.600293" and attempts[issuer]==1:
                raise TimeoutError("transient")
            if issuer=="sh.600301":
                raise HTTPError("https://www.cninfo.com.cn/",429,"throttle",{},None)
            return [{"historical_PIT_verified":False,"original_bytes_captured":False,
                     "announcement_id":"345"}]
        report=discover(*fixture(),client=client)
        self.assertEqual(attempts,{"sh.600293":2,"sh.600301":2,"sh.600363":1})
        self.assertEqual(report["transient_retry_issuers"],2)
        self.assertEqual(report["total_index_query_attempts"],5)
        self.assertEqual(report["index_unavailable"],1)
        self.assertEqual(report["index_candidates"],2)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])
        unsafe_calls={}
        def unsafe(issuer,research_window=None):
            unsafe_calls[issuer]=unsafe_calls.get(issuer,0)+1
            raise ValueError("forged source")
        blocked=discover(*fixture(),client=unsafe)
        self.assertEqual(sum(unsafe_calls.values()),3)
        self.assertEqual(blocked["total_index_query_attempts"],3)
        self.assertEqual(blocked["transient_retry_issuers"],0)
        self.assertEqual(blocked["index_unavailable"],3)
        self.assertEqual(blocked["historical_PIT_verified"],False)

    def test_forged_missing_duplicate_and_promoted_data_fail_closed(self):
        for scenario in ("epoch","missing","duplicate","asof_count","status",
                         "digest","asof_row","orders"):
            c,g=copy.deepcopy(fixture())
            if scenario=="epoch":g["source_epoch_sha256"]="b"*64
            if scenario=="missing":g["results"].pop()
            if scenario=="duplicate":g["results"][1]["issuer"]=g["results"][0]["issuer"]
            if scenario=="asof_count":c["gap_reason_counts"]["VENDOR_NOT_TRADABLE_ASOF"]=2
            if scenario=="status":g["results"][0]["official_halt_explanation_authenticated"]=True
            if scenario=="digest":g["results"][0]["original_csv_sha256"]="bad-sha"
            if scenario=="asof_row":g["results"][0]["trailing_vendor_suspended_rows"]=0
            if scenario=="orders":c["orders"]=[{"buy":True}]
            with self.subTest(scenario=scenario),self.assertRaises(ValueError):
                targets(c,g)

    def test_forged_index_pit_claim_is_never_accepted(self):
        c,g=fixture()
        report=discover(c,g,client=lambda issuer,research_window=None:[
            {"historical_PIT_verified":True,"original_bytes_captured":True}])
        self.assertEqual(report["index_unavailable"],3)
        self.assertEqual(report["index_candidates"],0)
        self.assertEqual(report["trade_gate"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
