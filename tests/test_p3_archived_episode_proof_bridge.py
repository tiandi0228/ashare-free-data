import copy
import unittest
from collector.p3_archived_episode_proof_bridge import bridge

DECISION="2026-11-11T14:30:00+08:00"


def fixture():
    digest="a"*64
    return {
        "phase":"P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH",
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "historical_PIT_verified":False,
        "historical_first_publication_authenticated":False,
        "complete_issuer_halt_intervals_certified":False,
        "official_PIT_cells_certified":0,
        "deduplicated_text_event_claims":1,
        "research_text_event_claims":[{
            "issuer":"sh.600421","announcement_id":"test123",
            "original_pdf_sha256":digest,
            "textual_direction":"HALT_START",
            "claimed_event_day":"2026-06-01",
            "first_publication_authenticated":False,
            "effective_date_certified":False,
            "historical_asof_trade_eligible":False,
            "source_text_date_is_not_complete_interval_proof":True,
            "research_capture_not_official_first_publication":True,
            "original_first_archived_research_run_id":123,
            "original_first_archived_research_capture_at_utc":"2026-11-11T06:00:00+00:00",
            "original_sha_verified_archive_path":
                f"pdf/sh_600421/test123/{digest}.pdf",
        }],
    }


class ArchivedEpisodeBridgeTests(unittest.TestCase):
    def test_archived_original_claim_becomes_blocked_research_task(self):
        result=bridge(fixture(),DECISION)
        self.assertEqual(result["research_issuer_claims"],1)
        self.assertEqual(result["proof_queue"]["task_count"],1)
        task=result["proof_queue"]["tasks"][0]
        self.assertEqual(task["research_action"],"VALIDATE_OFFICIAL_PUBLISHER_ORIGIN")
        self.assertEqual(result["publication_asof"]["known_event_count"],0)
        self.assertFalse(result["historical_PIT_verified"])
        self.assertEqual(result["orders"],[])
        self.assertFalse(task["trade_eligible"])

    def test_empty_archived_research_remains_empty(self):
        x=fixture()
        x["research_text_event_claims"]=[]
        x["deduplicated_text_event_claims"]=0
        result=bridge(x,DECISION)
        self.assertEqual(result["proof_queue"]["task_count"],0)

    def test_unsafe_claims_fail_closed(self):
        for field,value in (
            ("first_publication_authenticated",True),
            ("effective_date_certified",True),
            ("historical_asof_trade_eligible",True),
            ("source_text_date_is_not_complete_interval_proof",False),
            ("original_sha_verified_archive_path","wrong"),
            ("original_first_archived_research_capture_at_utc","2026-11-11T14:00:00"),
            ("original_pdf_sha256","invalid"),
            ("claimed_event_day","2026-06-99"),
        ):
            x=fixture()
            x["research_text_event_claims"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                bridge(x,DECISION)

    def test_missing_source_contract_or_repeated_origin_rejected(self):
        x=fixture();x["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):bridge(x,DECISION)
        x=fixture();x["research_text_event_claims"]*=2
        x["deduplicated_text_event_claims"]=2
        with self.assertRaises(ValueError):bridge(x,DECISION)
        x=fixture();x["deduplicated_text_event_claims"]=2
        with self.assertRaises(ValueError):bridge(x,DECISION)


if __name__=="__main__":
    unittest.main()
