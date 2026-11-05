"""SHA-anchored conflict packets demand independent official proofs."""
import copy,unittest
from collector.p3_event_proof_gap_queue import build as queue_build
from collector.p3_proof_gap_triage import build as triage_build
from collector.p3_conflict_review_packet import build
from tests.test_p3_event_proof_gap_queue import fixture

def triage():
    return triage_build(queue_build(fixture()))

class P3ConflictPacketTests(unittest.TestCase):
    def test_conflict_packet_keeps_both_sha_originals_and_no_pit(self):
        report=build(triage())
        self.assertEqual(report["priority_zero_conflicts"],1)
        self.assertEqual(report["source_queue_unresolved_items"],5)
        x=report["packets"][0]
        self.assertEqual(x["issuer"],"sh.600003")
        self.assertEqual([v["original_pdf_sha256"] for v in x["original_candidates"]],
                         ["e"*64,"f"*64])
        self.assertEqual([v["side"] for v in x["original_candidates"]],
                         ["PREVIOUS","NEXT"])
        self.assertEqual(len(x["missing_independent_proofs"]),4)
        self.assertFalse(x["historical_halt_interval_certified"])
        self.assertFalse(report["historical_PIT_verified"])
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])
    def test_repeated_same_notice_is_not_distinct_independent_original(self):
        s=fixture()
        s["overlap_conflicts"][0].update(next_announcement="115")
        report=build(triage_build(queue_build(s)))
        x=report["packets"][0]
        self.assertTrue(x["same_announcement_id_reused"])
        self.assertEqual(x["original_candidates"][0]["original_pdf_sha256"],
                         x["original_candidates"][1]["original_pdf_sha256"])
        self.assertFalse(report["historical_PIT_verified"])
    def test_missing_sha_anchor_and_claimed_certification_are_rejected(self):
        t=triage()
        mods=[
          lambda x:x.update(trade_gate="OPEN"),
          lambda x:x.update(official_state_intervals_certified=1),
          lambda x:x["work_items"][0].update(official_evidence_status="CERTIFIED"),
          lambda x:x["work_items"][0]["original_research_review_evidence"][
              "next_halt_original_sha_and_text_day_candidates"][0].update(
                   original_pdf_sha256="bad"),
          lambda x:x["work_items"][0]["original_research_review_evidence"][
              "previous_halt_original_sha_and_text_day_candidates"][0][
                   "archived_research_original_capture"].update(
                   official_first_publication_authenticated=True),
          lambda x:x["work_items"][0]["original_research_review_evidence"][
              "next_halt_original_sha_and_text_day_candidates"].clear(),
          lambda x:x["work_items"][0].update(priority=1),
        ]
        for mutation in mods:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                sample=copy.deepcopy(t);mutation(sample);build(sample)

if __name__=="__main__":unittest.main()
