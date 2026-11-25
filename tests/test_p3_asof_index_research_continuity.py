import copy
import unittest
from collector.p3_asof_index_research_continuity import recover

EPOCH="a"*64
CODES=["sz.002388","sz.002717","sz.002731"]


def source(unavailable=()):
    rows=[]
    for i,issuer in enumerate(CODES):
        missing=issuer in unavailable
        ident=str(12345+i)
        rows.append({
            "issuer":issuer,
            "original_vendor_csv_sha256":f"{i+1:064x}",
            "vendor_asof_date":"2026-10-20",
            "research_window_start":"2026-09-05",
            "research_window_end":"2026-10-27",
            "official_asof_state_authenticated":False,
            "independent_exchange_status_authenticated":False,
            "status":"INDEX_UNAVAILABLE_NOT_NO_RISK" if missing else "INDEX_CANDIDATES_UNVERIFIED",
            "candidates":[] if missing else [{
                "announcement_id":ident,
                "official_pdf_url":f"https://static.cninfo.com.cn/finalpage/2026-10-20/{ident}.PDF",
                "historical_PIT_verified":False,
                "original_bytes_captured":False,
            }],
        })
    return {"phase":"P3_THREE_ASOF_VENDOR_GAP_OFFICIAL_INDEX_RESEARCH",
            "source_epoch_sha256":EPOCH,
            "research_issuers":3,
            "index_candidates":3-len(unavailable),
            "index_unavailable":len(unavailable),
            "results":rows,
            "historical_first_publication_authenticated":False,
            "independent_exchange_status_authenticated":False,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"buy_signals":[]}


class PinnedSourceContinuityTests(unittest.TestCase):
    def test_only_unavailable_issuer_uses_old_leads_but_remains_unavailable(self):
        missing=[CODES[1]]
        result=recover(source(missing),source(),45319344709)
        self.assertEqual(result["current_index_unavailable"],1)
        self.assertEqual(result["current_index_candidates"],2)
        self.assertEqual(result["previous_research_lead_codes"],missing)
        self.assertEqual(result["previous_research_lead_issuers"],1)
        self.assertEqual(result["effective_discovery"]["index_candidates"],3)
        self.assertEqual(result["pdf_index_for_bounded_research"]["results"][1]["status"],
                         "PREVIOUS_RUN_INDEX_LEADS_RESEARCH_ONLY")
        item=result["effective_discovery"]["results"][1]
        self.assertEqual(item["current_index_status"],"INDEX_UNAVAILABLE_NOT_NO_RISK")
        self.assertTrue(item["current_index_was_unavailable"])
        self.assertTrue(item["research_leads_from_previous_run"])
        self.assertEqual(item["archived_research_source_run_id"],45319344709)
        self.assertEqual(result["historical_PIT_verified"],False)
        self.assertFalse(result["historical_first_publication_authenticated"])
        self.assertFalse(result["independent_exchange_status_authenticated"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_no_previous_artifact_preserves_unavailable(self):
        report=recover(source([CODES[2]]))
        self.assertEqual(report["previous_research_lead_issuers"],0)
        self.assertEqual(report["current_index_unavailable"],1)
        self.assertEqual(report["effective_discovery"]["index_candidates"],2)
        self.assertEqual(report["pdf_index_for_bounded_research"]["results"][2]["candidates"],[])
        self.assertEqual(report["trade_gate"],"BLOCKED")

    def test_no_stale_override_when_current_query_succeeds(self):
        report=recover(source(),source(),45319344709)
        self.assertEqual(report["previous_research_lead_issuers"],0)
        self.assertEqual(report["effective_discovery"]["index_candidates"],3)
        self.assertFalse(any(x["research_leads_from_previous_run"]
                             for x in report["effective_discovery"]["results"]))

    def test_previous_unavailable_does_not_create_false_candidates(self):
        result=recover(source([CODES[0]]),source([CODES[0]]),45319344709)
        self.assertEqual(result["previous_research_lead_issuers"],0)
        self.assertEqual(result["current_index_unavailable"],1)

    def test_forgeries_and_epoch_drift_fail_closed(self):
        for case in ("epoch","sha","asof","window","current_gate","previous_gate",
                     "previous_pit","candidate_pit","fake_url","count","duplicate","missing",
                     "run","publication"):
            current=source([CODES[1]])
            previous=source()
            run=45319344709
            if case=="epoch":previous["source_epoch_sha256"]="b"*64
            elif case=="sha":previous["results"][1]["original_vendor_csv_sha256"]="c"*64
            elif case=="asof":previous["results"][1]["vendor_asof_date"]="2026-10-19"
            elif case=="window":previous["results"][1]["research_window_start"]="2026-09-04"
            elif case=="current_gate":current["trade_gate"]="OPEN"
            elif case=="previous_gate":previous["orders"]=[{"buy":True}]
            elif case=="previous_pit":previous["historical_PIT_verified"]=True
            elif case=="candidate_pit":previous["results"][1]["candidates"][0]["historical_PIT_verified"]=True
            elif case=="fake_url":previous["results"][1]["candidates"][0]["official_pdf_url"]="https://fake.example/123.PDF"
            elif case=="count":previous["index_candidates"]=100
            elif case=="duplicate":previous["results"][1]["issuer"]=previous["results"][0]["issuer"]
            elif case=="missing":previous["results"].pop()
            elif case=="run":run=0
            elif case=="publication":previous["historical_first_publication_authenticated"]=True
            with self.subTest(case=case),self.assertRaises(ValueError):
                recover(current,previous,run)

if __name__=="__main__":
    unittest.main()
