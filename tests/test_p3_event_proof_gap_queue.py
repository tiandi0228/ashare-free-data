"""P3 research-only first-publication/effective-state gap queue contract tests."""
import copy
import unittest
from collector.p3_event_proof_gap_queue import build


def claim(code, action, day, digest, notice, approval=False):
    return {
        "issuer":code, "textual_direction":action,
        "claimed_event_day":day, "original_pdf_sha256":digest,
        "announcement_id":notice, "approval_not_effective_risk":approval,
        "first_publication_authenticated":False,
        "effective_date_certified":False,
        "historical_asof_trade_eligible":False,
    }


def fixture():
    a,b,c,d,e = ["sh.600001","sh.600002","sz.002002","sh.600003","sh.600004"]
    v = [
        claim(a,"HALT_START","2026-05-01","a"*64,"111"),
        claim(a,"RESUME_START","2026-05-06","b"*64,"112"),
        claim(b,"HALT_START","2026-04-01","c"*64,"113"),
        claim(c,"RESUME_START","2026-04-06","d"*64,"114"),
        claim(d,"HALT_START","2026-05-01","e"*64,"115",True),
        claim(d,"HALT_START","2026-05-02","f"*64,"116"),
    ]
    return {
        "phase":"P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH",
        "runs_replayed":153,
        "source_roster_epochs_observed":1,
        "unique_original_pdfs_sha_replayed":6,
        "raw_text_assertion_references":9,
        "deduplicated_text_event_claims":6,
        "duplicate_research_references_collapsed":3,
        "unpaired_halt_starts_needing_resumption_search":2,
        "paired_halt_resume_text_claims_unverified":1,
        "unpaired_resume_claims":1,
        "overlapping_halt_claims_without_resume":1,
        "approval_consent_is_not_effective_date_count":1,
        "research_text_event_claims":v,
        "paired_event_texts":[{
            "issuer":a,"halt_pdf_sha256":"a"*64,
            "resume_pdf_sha256":"b"*64,
            "halt_text_date":"2026-05-01",
            "resume_text_date":"2026-05-06",
            "status":"TWO_UNVERIFIED_TEXT_ASSERTIONS_NOT_CONTINUOUS_OFFICIAL_STATE",
            "historical_first_publication_authenticated":False,
            "issuer_interval_certified":False,
        }],
        "official_resumption_followups":[{
            "issuer":b,"halt_text_date":"2026-04-01",
            "halt_announcement_id":"113",
            "original_pdf_sha256":"c"*64,
            "historical_halt_interval_certified":False,
        },{
            "issuer":d,"halt_text_date":"2026-05-01",
            "halt_announcement_id":"115",
            "original_pdf_sha256":"e"*64,
            "historical_halt_interval_certified":False,
        }],
        "orphan_resume_texts":[{
            "issuer":c, "resumption_day_text":"2026-04-06",
        }],
        "overlap_conflicts":[{
            "issuer":d,
            "previous_announcement":"115",
            "next_announcement":"116",
        }],
        "historical_first_publication_authenticated":False,
        "complete_issuer_halt_intervals_certified":False,
        "official_PIT_cells_certified":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


class P3ProofQueueTests(unittest.TestCase):
    def test_replay_sha_linked_work_queue_without_pit_certification(self):
        r=build(fixture())
        self.assertEqual(r["status"],"UNVERIFIED_PIT_WORK_QUEUE_ONLY")
        self.assertEqual(r["work_item_count"],5)
        self.assertEqual(r["upstream_archived_runs_replayed"],153)
        self.assertEqual(r["upstream_unique_text_events"],6)
        self.assertEqual([x["priority"] for x in r["work_items"]],[0,1,2,2,3])
        self.assertEqual(r["work_items"][1]["halt_pdf_sha256"],"a"*64)
        self.assertIn("INDEPENDENT_FIRST_PUBLICATION_TIMESTAMP_FOR_BOTH_ORIGINALS",
                      r["work_items"][1]["missing_independent_proofs"])
        self.assertEqual(r["certified_first_publication_count"],0)
        self.assertEqual(r["certified_issuer_state_intervals"],0)
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
        self.assertEqual(r["recommendations"],[])
    def test_upgraded_source_status_or_mismatch_rejected(self):
        for changes in (
            {"trade_gate":"OPEN"}, {"historical_PIT_verified":True},
            {"official_PIT_cells_certified":1},
            {"historical_first_publication_authenticated":True},
            {"complete_issuer_halt_intervals_certified":True},
            {"orders":[{"side":"BUY"}]},
            {"deduplicated_text_event_claims":5},
            {"paired_halt_resume_text_claims_unverified":2},
            {"raw_text_assertion_references":0},
            {"approval_consent_is_not_effective_date_count":0},
        ):
            with self.subTest(changes=changes):
                sample=fixture()
                sample.update(changes)
                with self.assertRaises(ValueError):
                    build(sample)
    def test_invalid_pdf_anchor_ambiguous_or_date_cannot_certify(self):
        mutations=(
            lambda s:s["paired_event_texts"][0].update(resume_pdf_sha256="0"*64),
            lambda s:s["paired_event_texts"][0].update(halt_text_date="2026-06-07"),
            lambda s:s["paired_event_texts"][0].update(issuer_interval_certified=True),
            lambda s:s["paired_event_texts"][0].update(halt_text_date="2026-05-07"),
            lambda s:s["research_text_event_claims"][0].update(original_pdf_sha256="BAD"),
            lambda s:s["research_text_event_claims"][0].update(first_publication_authenticated=True),
            lambda s:s["official_resumption_followups"][0].update(original_pdf_sha256="0"*64),
            lambda s:s["orphan_resume_texts"][0].update(issuer="sz.002999"),
            lambda s:s["overlap_conflicts"][0].update(next_announcement="untrusted"),
        )
        for change in mutations:
            with self.subTest(change=change):
                sample=fixture()
                change(sample)
                with self.assertRaises(ValueError):
                    build(sample)
    def test_no_event_claims_remains_unverified_without_new_pit(self):
        s=fixture()
        for k in ("research_text_event_claims","paired_event_texts",
                  "official_resumption_followups","orphan_resume_texts",
                  "overlap_conflicts"):
            s[k]=[]
        for k in ("raw_text_assertion_references","deduplicated_text_event_claims",
                  "unpaired_halt_starts_needing_resumption_search",
                  "paired_halt_resume_text_claims_unverified","unpaired_resume_claims",
                  "overlapping_halt_claims_without_resume",
                  "approval_consent_is_not_effective_date_count"):
            s[k]=0
        r=build(s)
        self.assertEqual(r["work_item_count"],0)
        self.assertFalse(r["historical_PIT_verified"])


if __name__=="__main__":
    unittest.main()
