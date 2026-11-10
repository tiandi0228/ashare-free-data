import copy
import unittest
from collector.p3_gap_original_provenance_index import index

EPOCH="a"*64
DOC="b"*64
RESUME="c"*64


def fixtures():
    queue={
        "phase":"P2_P3_SOURCE_SHA_ISSUER_EVIDENCE_REVIEW_QUEUE",
        "status":"UNRESOLVED_OFFICIAL_PROOF_REQUIREMENTS_RESEARCH_ONLY",
        "source_epoch_sha256":EPOCH,"gap_issuer_count":2,
        "p2_source_run_id":42723193588,"p3_source_run_id":42723131727,
        "unresolved_issuer_count":2,"official_halt_intervals_certified":0,
        "feature_gaps_resolved":0,"historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "tasks":[
            {"issuer":"sh.600001","source_epoch_sha256":EPOCH,
             "original_vendor_csv_sha256":"d"*64,
             "research_action":"AUTHENTICATE_BOTH_ORIGINAL_PUBLICATION_TIMES_AND_EFFECTIVE_INTERVAL",
             "official_pdf_halt_resume_text_leads":1,
             "research_text_resume_pairs":1,
             "historical_PIT_verified":False,
             "feature_gap_resolved":False,
             "official_evidence_authenticated":False,"buy_eligible":False},
            {"issuer":"sh.600002","source_epoch_sha256":EPOCH,
             "original_vendor_csv_sha256":"e"*64,
             "research_action":"FIND_ORIGINAL_HALT_RESUME_ANNOUNCEMENTS",
             "official_pdf_halt_resume_text_leads":0,
             "research_text_resume_pairs":0,
             "historical_PIT_verified":False,
             "feature_gap_resolved":False,
             "official_evidence_authenticated":False,"buy_eligible":False},
        ]}
    events={
        "phase":"P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH",
        "trade_gate":"BLOCKED","orders":[],
        "historical_PIT_verified":False,
        "historical_first_publication_authenticated":False,
        "official_PIT_cells_certified":0,
        "deduplicated_text_event_claims":1,
        "research_text_event_claims":[{
            "issuer":"sh.600001","textual_direction":"HALT_START",
            "announcement_id":"123","original_pdf_sha256":DOC,
            "claimed_event_day":"2025-03-10",
            "original_first_archived_research_capture_at_utc":"2026-11-09T11:25:30+00:00",
            "original_sha_verified_archive_path":"pdf/sh_600001/123/"+DOC+".pdf",
            "research_capture_not_official_first_publication":True,
            "first_publication_authenticated":False,
            "effective_date_certified":False,
            "historical_asof_trade_eligible":False}]}
    pairs={
        "phase":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
        "trade_gate":"BLOCKED","orders":[],
        "historical_PIT_verified":False,
        "authenticated_first_publication_count":0,
        "official_halt_resume_intervals_certified":0,
        "deduplicated_research_text_pairs":1,
        "text_only_halt_resume_pairs":[{
            "issuer":"sh.600001","halt_original_sha256":DOC,
            "resume_original_sha256":RESUME,
            "halt_text_date":"2025-03-10","resume_text_date":"2025-04-10",
            "historical_first_publication_verified":False,
            "official_resume_effective_date_verified":False,
            "whole_interval_tradability_verified":False}]}
    return queue,events,pairs


class OriginalProofSourceIndexTests(unittest.TestCase):
    def test_same_issuer_sha_document_and_archival_capture_not_publication(self):
        out=index(*fixtures())
        self.assertEqual(out["gap_issuer_count"],2)
        self.assertEqual(out["p2_source_run_id"],42723193588)
        self.assertEqual(out["p3_source_run_id"],42723131727)
        self.assertTrue(out["source_run_ids_are_research_artifact_locators_only"])
        self.assertEqual(out["issuer_with_original_halt_resume_text"],1)
        self.assertEqual(out["issuer_with_resume_text_pair"],1)
        self.assertEqual(out["total_source_document_text_leads"],1)
        row=out["issuers"][0]
        self.assertEqual(row["issuer"],"sh.600001")
        pdf=row["original_halt_resume_text_documents"][0]
        self.assertEqual(pdf["original_pdf_sha256"],DOC)
        self.assertEqual(pdf["claimed_event_text_date"],"2025-03-10")
        self.assertEqual(pdf["first_research_capture_at_utc"],"2026-11-09T11:25:30+00:00")
        self.assertTrue(pdf["collection_time_is_not_first_publication"])
        self.assertFalse(pdf["historical_first_publication_authenticated"])
        self.assertFalse(row["buy_eligible"])
        self.assertEqual(out["authenticated_first_publication_count"],0)
        self.assertEqual(out["certified_exchange_intervals"],0)
        self.assertEqual(out["trade_gate"],"BLOCKED")
        self.assertEqual(out["orders"],[])

    def test_missing_pdf_or_pair_evidence_cannot_keep_existing_task_count(self):
        for what in ("doc","pair"):
            queue,events,pairs=copy.deepcopy(fixtures())
            if what=="doc":
                events["research_text_event_claims"]=[]
                events["deduplicated_text_event_claims"]=0
            else:
                pairs["text_only_halt_resume_pairs"]=[]
                pairs["deduplicated_research_text_pairs"]=0
            with self.subTest(what=what),self.assertRaises(ValueError):
                index(queue,events,pairs)

    def test_forged_pit_and_original_digest_rejected(self):
        for item,value in (
            ("first_publication_authenticated",True),
            ("effective_date_certified",True),
            ("historical_asof_trade_eligible",True),
            ("original_pdf_sha256","not-a-SHA"),
            ("original_sha_verified_archive_path","pdf/fake.pdf"),
            ("original_first_archived_research_capture_at_utc","2025-01-01T10:00:00"),
            ("research_capture_not_official_first_publication",False),
        ):
            q,e,p=copy.deepcopy(fixtures())
            e["research_text_event_claims"][0][item]=value
            with self.subTest(item=item),self.assertRaises(ValueError):
                index(q,e,p)

    def test_original_pdf_path_must_bind_exact_issuer_and_announcement(self):
        for field,value in (
            ("original_sha_verified_archive_path",
             "pdf/sh_600002/123/"+DOC+".pdf"),
            ("original_sha_verified_archive_path",
             "pdf/sh_600001/999/"+DOC+".pdf"),
            ("original_sha_verified_archive_path",
             "untrusted/pdf/sh_600001/123/"+DOC+".pdf"),
            ("original_sha_verified_archive_path",
             "pdf/sh_600001/123/"+DOC+".pdf/extra"),
            ("announcement_id","not-a-number"),
        ):
            q,e,p=copy.deepcopy(fixtures())
            e["research_text_event_claims"][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                index(q,e,p)

    def test_same_issuer_resume_chronology_and_sha_mandatory(self):
        for key,value in (
            ("whole_interval_tradability_verified",True),
            ("official_resume_effective_date_verified",True),
            ("historical_first_publication_verified",True),
            ("resume_original_sha256","missing"),
            ("resume_text_date","2024-01-01"),
        ):
            q,e,p=copy.deepcopy(fixtures())
            p["text_only_halt_resume_pairs"][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                index(q,e,p)

    def test_source_run_id_forgery_rejected_without_promoting_official_status(self):
        for key,value in (
            ("p2_source_run_id",None),
            ("p2_source_run_id",False),
            ("p2_source_run_id",0),
            ("p2_source_run_id","42723193588"),
            ("p3_source_run_id",-1),
            ("p3_source_run_id",True),
        ):
            q,e,p=copy.deepcopy(fixtures())
            q[key]=value
            with self.subTest(key=key,value=value),self.assertRaisesRegex(
                ValueError,"source run IDs"):
                index(q,e,p)
        out=index(*fixtures())
        self.assertEqual(out["authenticated_first_publication_count"],0)
        self.assertEqual(out["certified_exchange_intervals"],0)
        self.assertFalse(out["historical_PIT_verified"])
        self.assertEqual(out["trade_gate"],"BLOCKED")
        self.assertEqual(out["orders"],[])

    def test_cross_epoch_task_duplicates_and_count_fraud_rejected(self):
        for case in ("epoch","duplicate","count","gate"):
            q,e,p=copy.deepcopy(fixtures())
            if case=="epoch":q["tasks"][0]["source_epoch_sha256"]="f"*64
            elif case=="duplicate":q["tasks"][1]["issuer"]=q["tasks"][0]["issuer"]
            elif case=="count":q["gap_issuer_count"]=3
            else:q["trade_gate"]="OPEN"
            with self.subTest(case=case),self.assertRaises(ValueError):
                index(q,e,p)

if __name__=="__main__":
    unittest.main()
