"""P3 index time is a cross-checked lead, never historical PIT proof."""
import copy
import unittest
from datetime import datetime, timezone

from collector.p3_index_chronology_guard import audit


def ms(year, month, day, hour, minute=0):
    return int(datetime(year, month, day, hour, minute,
                        tzinfo=timezone.utc).timestamp()*1000)


def snapshot(index_ms=None, klass=None, decision="2026-04-18",
             captured="2026-11-04T03:00:00+00:00"):
    if index_ms is None:
        index_ms=ms(2026, 4, 18, 6, 30)  # 14:30 Beijing, before 15:00 close.
    source={
        "issuer":"sh.600038", "announcement_id":"123456789",
        "pdf_sha256":"a"*64, "original_retrieved":True,
        "index_publication_milliseconds_unverified":index_ms,
        "captured_at_utc":captured,
        "historical_PIT_verified":False,
        "historical_first_publication_authenticated":False,
        "effective_date_authenticated":False,
    }
    known=type(index_ms) is int and 1000000000000<=index_ms<=2100000000000
    date_text=datetime.fromtimestamp(index_ms/1000,timezone.utc).isoformat() if known else None
    if klass is None:
        klass=("INDEX_TIME_NOT_AFTER_DECISION_CLOSE_UNVERIFIED"
               if known else "INDEX_PUBLICATION_TIME_MISSING_UNVERIFIED")
    link={
        "issuer":"sh.600038", "announcement_id":"123456789",
        "original_pdf_sha256":"a"*64, "decision_day":decision,
        "claimed_index_publication_utc_unverified":date_text,
        "index_time_screen":klass,
        "effective_date_authenticated":False,
        "first_publication_authenticated":False,
        "decision_time_available_certified":False,
    }
    return {
        "phase":"P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE",
        "trade_gate":"BLOCKED", "orders":[], "executable_candidates":[],
        "historical_PIT_verified":False,
        "certified_first_publication_count":0,
        "certified_event_effective_day_count":0,
        "certified_historical_decision_state_count":0,
        "source_pdf_receipts":[source],
        "research_date_action_links":[link],
        "original_pdf_count":1, "run_id":42,
    }


class IndependentChronologyTests(unittest.TestCase):
    def test_consistent_preclose_index_is_only_research(self):
        result=audit(snapshot())
        self.assertEqual(result["status"],
                         "INDEX_CHRONOLOGY_CROSSCHECK_RESEARCH_ONLY")
        self.assertEqual(result["research_links_rechecked"],1)
        self.assertEqual(result["index_not_after_decision_close_unverified"],1)
        self.assertEqual(result["index_after_decision_close_unverified"],0)
        self.assertEqual(result["certified_first_publication_times"],0)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
        self.assertFalse(result["trade_authorized"])

    def test_after_close_index_class_rebuilt_and_remains_uncertified(self):
        p=snapshot(index_ms=ms(2026,4,18,8),
                   klass="INDEX_TIME_AFTER_DECISION_CLOSE_UNVERIFIED")
        result=audit(p)
        self.assertEqual(result["index_after_decision_close_unverified"],1)
        self.assertEqual(result["certified_first_publication_times"],0)

    def test_missing_index_time_is_not_certified_preclose(self):
        p=snapshot(index_ms=None)
        p["source_pdf_receipts"][0]["index_publication_milliseconds_unverified"]=None
        p["research_date_action_links"][0].update(
            index_time_screen="INDEX_PUBLICATION_TIME_MISSING_UNVERIFIED",
            claimed_index_publication_utc_unverified=None)
        result=audit(p)
        self.assertEqual(result["status"],"INDEX_CHRONOLOGY_CROSSCHECK_RESEARCH_ONLY")
        self.assertEqual(result["index_time_missing_or_malformed"],1)

    def test_forged_time_class_is_rejected(self):
        p=snapshot(index_ms=ms(2026,4,18,8),
                   klass="INDEX_TIME_NOT_AFTER_DECISION_CLOSE_UNVERIFIED")
        self.assertEqual(audit(p)["reason"],
                         "CONTRADICTORY_INDEX_TIME_OR_DECISION_CLASSIFICATION")

    def test_forged_index_utc_and_pdf_sha_rejected(self):
        p=snapshot()
        p["research_date_action_links"][0]["claimed_index_publication_utc_unverified"]="2026-04-18T00:00:00+00:00"
        self.assertEqual(audit(p)["reason"],
                         "CONTRADICTORY_INDEX_TIME_OR_DECISION_CLASSIFICATION")
        p=snapshot()
        p["research_date_action_links"][0]["original_pdf_sha256"]="b"*64
        self.assertEqual(audit(p)["reason"],
                         "LINK_SOURCE_OR_CERTIFICATION_MISMATCH")

    def test_naive_capture_or_fake_certificate_rejected(self):
        p=snapshot(captured="2026-11-04T03:00:00")
        self.assertEqual(audit(p)["status"],"REJECTED")
        p=snapshot()
        p["research_date_action_links"][0]["first_publication_authenticated"]=True
        self.assertEqual(audit(p)["status"],"REJECTED")
        p=snapshot()
        p["certified_first_publication_count"]=1
        self.assertEqual(audit(p)["reason"],"UNSAFE_ARCHIVED_SOURCE_MANIFEST")

    def test_mutable_index_timestamp_after_capture_is_flagged_not_certified(self):
        p=snapshot(index_ms=ms(2026,4,18,8),
                   klass="INDEX_TIME_AFTER_DECISION_CLOSE_UNVERIFIED",
                   captured="2026-04-17T00:00:00+00:00")
        result=audit(p)
        self.assertEqual(result["index_later_than_capture_suspect"],1)
        self.assertEqual(result["certified_first_publication_times"],0)

    def test_wrong_issuer_receipt_duplicate_or_source_count_rejected(self):
        p=snapshot()
        p["source_pdf_receipts"][0]["issuer"]="sz.002249"
        self.assertEqual(audit(p)["reason"],"LINK_WITHOUT_ARCHIVED_ORIGINAL")
        p=snapshot()
        p["source_pdf_receipts"].append(copy.deepcopy(p["source_pdf_receipts"][0]))
        self.assertEqual(audit(p)["reason"],"DUPLICATE_ORIGINAL_RECEIPT")
        p=snapshot()
        p["original_pdf_count"]=2
        self.assertEqual(audit(p)["reason"],"ORIGINAL_RECEIPT_COUNT_MISMATCH")

    def test_before_close_unverified_never_means_available_when_captured_later(self):
        p=snapshot()
        result=audit(p)
        self.assertEqual(result["captured_after_decision_date"],1)
        self.assertFalse(result["source_sha_linked_chronology_checks"][0][
            "historical_asof_usable"])


if __name__=="__main__":
    unittest.main()
