import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from collector.p3_asof_publication_chronology_triage import triage
from collector.p3_asof_original_notice_review_packets import build
from tests.test_p3_asof_original_notice_review_packets import fixture

EPOCH="b"*64


def sources():
    cross,ctx=fixture()
    index_time=int(datetime(2026,10,22,10,30,tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()*1000)
    for i,lead in enumerate(cross["leads"]):
        lead["index_timestamp_unverified"]=index_time if i==0 else None
        lead["index_source_scope"]="CURRENT_INDEX_RESEARCH_UNVERIFIED"
        lead["archived_research_source_run_id"]=None
        lead["current_index_status"]="INDEX_CANDIDATES_UNVERIFIED"
    packets=build(cross,ctx)
    discovery={
        "phase":"P3_THREE_ASOF_VENDOR_GAP_OFFICIAL_INDEX_RESEARCH",
        "source_epoch_sha256":EPOCH,
        "trade_gate":"BLOCKED","orders":[],"historical_PIT_verified":False,
        "results":[
            {"issuer":"sz.002388","vendor_asof_date":"2026-10-20",
             "original_vendor_csv_sha256":"c"*64,
             "official_asof_state_authenticated":False,
             "independent_exchange_status_authenticated":False,
             "status":"INDEX_CANDIDATES_UNVERIFIED",
             "current_index_status":"INDEX_CANDIDATES_UNVERIFIED",
             "research_leads_from_previous_run":False,
             "archived_research_source_run_id":None,
             "candidates":[{"announcement_id":"123",
               "official_pdf_url":"https://static.cninfo.com.cn/finalpage/2026-10-20/123.PDF",
               "index_published_milliseconds_unverified":index_time,
               "historical_PIT_verified":False,"original_bytes_captured":False}]},
            {"issuer":"sz.002717","vendor_asof_date":"2026-10-20",
             "original_vendor_csv_sha256":"d"*64,
             "official_asof_state_authenticated":False,
             "independent_exchange_status_authenticated":False,
             "status":"NO_INDEX_MATCH_NOT_NO_RISK","candidates":[],
             "current_index_status":"NO_INDEX_MATCH_NOT_NO_RISK",
             "research_leads_from_previous_run":False,
             "archived_research_source_run_id":None},
            {"issuer":"sz.002731","vendor_asof_date":"2026-10-20",
             "original_vendor_csv_sha256":"e"*64,
             "official_asof_state_authenticated":False,
             "independent_exchange_status_authenticated":False,
             "status":"NO_INDEX_MATCH_NOT_NO_RISK","candidates":[],
             "current_index_status":"NO_INDEX_MATCH_NOT_NO_RISK",
             "research_leads_from_previous_run":False,
             "archived_research_source_run_id":None},
        ]}
    return packets,cross,discovery


class IndexChronologyTests(unittest.TestCase):
    def test_unverified_timestamp_later_than_event_is_only_a_research_warning(self):
        report=triage(*sources())
        self.assertEqual(report["reviewed_date_contexts"],2)
        self.assertEqual(report["priority_review_candidates"],1)
        self.assertEqual(report["index_after_event_day_research_warnings"],1)
        self.assertEqual(report["index_after_vendor_asof_research_warnings"],1)
        one=next(x for x in report["review_rows"]
                 if x["index_vs_event_date_research_classification"]=="INDEX_AFTER_EVENT_DAY_REVIEW_REQUIRED")
        self.assertEqual(one["text_event_day_unverified"],"2026-10-20")
        self.assertEqual(one["cninfo_index_time_shanghai_unverified"][:10],"2026-10-22")
        self.assertFalse(one["first_publication_time_independently_authenticated"])
        self.assertFalse(one["exchange_state_interval_certified"])
        self.assertFalse(one["buy_eligible"])
        self.assertEqual(report["authenticated_first_publication_count"],0)
        self.assertEqual(report["certified_exchange_intervals"],0)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])

    def test_source_timestamp_before_event_is_not_a_certificate(self):
        packet,cross,discovery=sources()
        cross["leads"][0]["index_timestamp_unverified"]=int(
            datetime(2026,10,19,16,tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()*1000)
        discovery["results"][0]["candidates"][0]["index_published_milliseconds_unverified"]=cross["leads"][0]["index_timestamp_unverified"]
        out=triage(packet,cross,discovery)
        self.assertEqual(out["index_after_event_day_research_warnings"],0)
        self.assertEqual(out["authenticated_first_publication_count"],0)
        self.assertFalse(out["historical_PIT_verified"])

    def test_forged_timestamp_or_source_identity_fails_closed(self):
        for case in ("epoch","timestamp_bool","timestamp_string","timestamp_nan",
                     "duplicate","bad_date","bad_issuer","doc_sha","source_pit",
                     "gate","review_pit","url"):
            packet,cross,discovery=copy.deepcopy(sources())
            if case=="epoch":discovery["source_epoch_sha256"]="f"*64
            elif case=="timestamp_bool":cross["leads"][0]["index_timestamp_unverified"]=True
            elif case=="timestamp_string":cross["leads"][0]["index_timestamp_unverified"]="1792640000000"
            elif case=="timestamp_nan":cross["leads"][0]["index_timestamp_unverified"]=-1
            elif case=="duplicate":packet["review_queue"].append(copy.deepcopy(packet["review_queue"][0]));packet["total_contexts"]=3
            elif case=="bad_date":packet["review_queue"][0]["source_date_text_unverified"]="2026年2月30日"
            elif case=="bad_issuer":discovery["results"][0]["issuer"]="sz.002860"
            elif case=="doc_sha":packet["review_queue"][0]["original_pdf_sha256"]="f"*64
            elif case=="source_pit":cross["leads"][0]["historical_first_publication_authenticated"]=True
            elif case=="gate":discovery["trade_gate"]="OPEN"
            elif case=="review_pit":packet["official_first_publication_authenticated"]=1
            elif case=="url":packet["review_queue"][0]["original_pdf_url_unverified"]="https://example.com/forged.pdf"
            with self.subTest(case=case),self.assertRaises(ValueError):
                triage(packet,cross,discovery)

    def test_tampered_index_time_or_notice_or_run_fails_closed(self):
        for case in ("index_time","index_absent","wrong_notice","wrong_url",
                     "unsafe_doc","wrong_scope","wrong_run","wrong_status"):
            packet,cross,discovery=copy.deepcopy(sources())
            candidate=discovery["results"][0]["candidates"][0]
            if case=="index_time":
                candidate["index_published_milliseconds_unverified"]+=86400000
            elif case=="index_absent":
                candidate["index_published_milliseconds_unverified"]=None
            elif case=="wrong_notice":
                candidate["announcement_id"]="456"
            elif case=="wrong_url":
                candidate["official_pdf_url"]="https://static.cninfo.com.cn/finalpage/2026-10-20/456.PDF"
            elif case=="unsafe_doc":
                candidate["historical_PIT_verified"]=True
            elif case=="wrong_scope":
                cross["leads"][0]["index_source_scope"]="ARCHIVED_RESEARCH_LEAD_NOT_CURRENT_QUERY"
            elif case=="wrong_run":
                packet["review_queue"][0]["archived_research_source_run_id"]=45319344709
            elif case=="wrong_status":
                discovery["results"][0]["status"]="UNTRUSTED_SOURCE"
            with self.subTest(case=case),self.assertRaises(ValueError):
                triage(packet,cross,discovery)

    def test_archived_lead_preserves_source_run_and_does_not_become_pit(self):
        packet,cross,discovery=sources()
        cross["leads"][0]["index_source_scope"]="ARCHIVED_RESEARCH_LEAD_NOT_CURRENT_QUERY"
        cross["leads"][0]["archived_research_source_run_id"]=45319344709
        packet["review_queue"][0]["index_source_scope"]="ARCHIVED_RESEARCH_LEAD_NOT_CURRENT_QUERY"
        packet["review_queue"][0]["archived_research_source_run_id"]=45319344709
        packet["review_queue"][0]["current_index_status"]="INDEX_UNAVAILABLE_NOT_NO_RISK"
        cross["leads"][0]["current_index_status"]="INDEX_UNAVAILABLE_NOT_NO_RISK"
        discovery["results"][0].update({
            "status":"PREVIOUS_RUN_INDEX_LEADS_RESEARCH_ONLY",
            "current_index_status":"INDEX_UNAVAILABLE_NOT_NO_RISK",
            "current_index_was_unavailable":True,
            "research_leads_from_previous_run":True,
            "archived_research_source_run_id":45319344709})
        report=triage(packet,cross,discovery)
        lead=next(x for x in report["review_rows"]
                  if x["index_source_scope"]=="ARCHIVED_RESEARCH_LEAD_NOT_CURRENT_QUERY")
        self.assertEqual(lead["archived_research_source_run_id"],45319344709)
        self.assertFalse(lead["historical_PIT_verified"])
        self.assertEqual(report["trade_gate"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
