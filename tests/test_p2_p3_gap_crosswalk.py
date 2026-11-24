import copy
import unittest
from collector.p2_p3_gap_crosswalk import crosswalk

def samples():
    gaps={"phase":"P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS",
        "source_epoch_sha256":"a"*64,
        "status":"SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "coverage_gaps_resolved":0,"orders":[],
        "research_gap_issuers":2,
        "results":[
            {"issuer":"sh.600001","diagnosis":"VENDOR_SUSPENDED_ROW_WITHIN_LAST_21",
             "asof_date":"2025-12-31","trailing_vendor_suspended_rows":2,
             "original_csv_sha256":"a"*64,"official_halt_explanation_authenticated":False},
            {"issuer":"sz.002001","diagnosis":"FEWER_THAN_21_VENDOR_ROWS_ASOF",
             "asof_date":"2025-12-31","trailing_vendor_suspended_rows":0,
             "original_csv_sha256":"b"*64,"official_halt_explanation_authenticated":False}]}
    events={"phase":"P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "official_PIT_cells_certified":0,
        "complete_issuer_halt_intervals_certified":False,
        "historical_first_publication_authenticated":False,
        "orders":[],"research_text_event_claims":[
            {"issuer":"sh.600001","textual_direction":"HALT_START",
             "first_publication_authenticated":False,"effective_date_certified":False,
             "historical_asof_trade_eligible":False}]}
    pairs={"phase":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "official_halt_resume_intervals_certified":0,
        "authenticated_first_publication_count":0,"orders":[],
        "deduplicated_research_text_pairs":1,
        "text_only_halt_resume_pairs":[{
            "issuer":"sh.600001","historical_first_publication_verified":False,
            "official_resume_effective_date_verified":False,
            "whole_interval_tradability_verified":False}]}
    return gaps,events,pairs

class CrosswalkTests(unittest.TestCase):
    def test_same_issuer_join_not_official_interval(self):
        result=crosswalk(*samples())
        self.assertEqual(result["gap_issuers_examined"],2)
        self.assertEqual(result["gap_issuers_with_same_issuer_official_pdf_text_lead"],1)
        self.assertEqual(result["gap_issuers_with_same_issuer_resume_text_pair"],1)
        self.assertEqual(result["official_halt_intervals_authenticated"],0)
        self.assertEqual(result["feature_gaps_resolved"],0)
        self.assertFalse(result["issuer_evidence"][0]["gap_resolved"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_forged_certification_or_duplicates_fail(self):
        for i,key,value in (
            (0,"coverage_gaps_resolved",1),
            (1,"official_PIT_cells_certified",1),
            (2,"authenticated_first_publication_count",1)):
            records=copy.deepcopy(samples())
            records[i][key]=value
            with self.assertRaises(ValueError):crosswalk(*records)
        records=copy.deepcopy(samples())
        records[0]["results"][1]["issuer"]="sh.600001"
        with self.assertRaises(ValueError):crosswalk(*records)
    def test_corrupt_identifiers_and_digest_fail_closed(self):
        cases=[
            (0,"results",0,"issuer","not-an-issuer"),
            (0,"results",0,"original_csv_sha256","bogus"),
            (0,"results",0,"trailing_vendor_suspended_rows",-1),
            (0,"results",0,"trailing_vendor_suspended_rows",True),
            (1,"research_text_event_claims",0,"issuer","not-an-issuer"),
            (1,"research_text_event_claims",0,"textual_direction","SUSPENDED"),
            (2,"text_only_halt_resume_pairs",0,"issuer","not-an-issuer"),
        ]
        for source,collection,index,field,value in cases:
            with self.subTest(source=source,field=field,value=value):
                records=copy.deepcopy(samples())
                records[source][collection][index][field]=value
                with self.assertRaises(ValueError):
                    crosswalk(*records)
    def test_non_halt_p3_events_are_valid_but_not_halt_evidence(self):
        for direction in ("ST_APPLIED","ST_REMOVED","LISTING_START","DELIST_EFFECTIVE"):
            with self.subTest(direction=direction):
                records=copy.deepcopy(samples())
                records[1]["research_text_event_claims"][0]["textual_direction"]=direction
                result=crosswalk(*records)
                self.assertEqual(result["gap_issuers_with_same_issuer_official_pdf_text_lead"],0)
                self.assertEqual(result["gap_issuers_with_same_issuer_resume_text_pair"],1)
                self.assertFalse(result["issuer_evidence"][0]["gap_resolved"])
                self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_three_asof_nontradable_gaps_crosswalk_without_pit_promotion(self):
        gaps,events,pairs=samples()
        for n in range(3):
            gaps["results"].append({
                "issuer":f"sz.{300100+n:06d}",
                "diagnosis":"VENDOR_MARKED_NOT_TRADABLE_AT_ASOF",
                "asof_date":"2026-10-20",
                "trailing_vendor_suspended_rows":1,
                "original_csv_sha256":f"{n+1:064x}",
                "official_halt_explanation_authenticated":False,
            })
        gaps["research_gap_issuers"]=5
        result=crosswalk(gaps,events,pairs)
        self.assertEqual(result["gap_issuers_examined"],5)
        self.assertEqual(sum(r["vendor_gap_diagnosis"]=="VENDOR_MARKED_NOT_TRADABLE_AT_ASOF"
                             for r in result["issuer_evidence"]),3)
        self.assertTrue(all(r["official_trading_state_covered_for_gap"] is False
                            and r["gap_resolved"] is False
                            for r in result["issuer_evidence"]))
        self.assertEqual(result["official_halt_intervals_authenticated"],0)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

        gaps["results"][-1]["trailing_vendor_suspended_rows"]=0
        with self.assertRaisesRegex(ValueError,"contradicts"):
            crosswalk(gaps,events,pairs)

    def test_empty_bounded_p3_research_not_negative_proof(self):
        gaps,events,pairs=samples()
        events["research_text_event_claims"]=[]
        pairs["text_only_halt_resume_pairs"]=[]
        pairs["deduplicated_research_text_pairs"]=0
        result=crosswalk(gaps,events,pairs)
        self.assertEqual(result["gap_issuers_with_same_issuer_official_pdf_text_lead"],0)
        self.assertEqual(result["official_halt_intervals_authenticated"],0)

if __name__=="__main__":unittest.main()
