"""Readiness matrix must not mistake shard or offline test progress for tradability."""
import copy,unittest
from collector.parallel_readiness_matrix import summarize,LANES
from collector.parallel_research_contracts import blocked

def ledger(done):
    count=4
    return {"phase":"P1_ROSTER_SHARD_LEDGER","source_sha256":"a"*64,
            "shard_count":count,"completed":[
              {"index":i,"issuer_count":8,"manifest_sha256":"b"*64,
               "receipt_sha256":"c"*64} for i in range(done)],
            "completed_shards":done,"completed_issuers":done*8,
            "pending_shards":list(range(done,4)),
            "next_shard":done if done<4 else None,
            "failed_in_this_reconciliation":[],
            "full_market_bars_certified":False,"historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def reports():
    return {k:blocked(v,"STRUCTURAL_TEST_ONLY",["NOT_VERIFIED"],lane=v)
            for k,v in LANES.items()}
class ReadinessMatrixTests(unittest.TestCase):
    def test_complete_ingestion_never_unblocks_anything(self):
        x=summarize(ledger(4),reports())
        self.assertEqual(x["history"]["ingestion_percentage"],100)
        self.assertEqual(x["history"]["status"],"INGESTION_SHARDS_COMPLETE_NOT_CERTIFIED")
        self.assertIsNone(x["overall_project_percentage"])
        self.assertFalse(x["production_ready"])
        self.assertEqual(x["trade_gate"],"BLOCKED")
        self.assertEqual(x["orders"],[])
        for key in LANES:
            self.assertFalse(x["lanes"][key]["production_certified"])
            self.assertTrue(x["lanes"][key]["structural_evidence_received"])
    def test_progress_is_denominator_based(self):
        x=summarize(ledger(1),{})
        self.assertEqual(x["history"]["ingestion_percentage"],25)
        self.assertEqual(x["history"]["completed_issuers"],8)
        self.assertEqual(x["lanes"]["ranking"]["status"],"EVIDENCE_MISSING_OR_INVALID")
    def test_lanes_with_fake_certification_are_invalid(self):
        p=reports()
        p["quotes"]["certified"]=True
        p["pit"]["trade_gate"]="OPEN"
        p["forward"]["orders"]=[{"side":"BUY"}]
        p["ranking"]["actionable_buy_signals"]=["600000"]
        x=summarize(ledger(2),p)
        self.assertTrue(all(v["status"]=="EVIDENCE_MISSING_OR_INVALID"
                            for v in x["lanes"].values()))
        self.assertEqual(x["trade_gate"],"BLOCKED")
    def test_bad_checkpoint_never_used_for_completion(self):
        x=ledger(4);x["completed_issuers"]=999
        r=summarize(x,reports())
        self.assertEqual(r["history"]["status"],"CHECKPOINT_INVALID")
        self.assertIsNone(r["history"]["ingestion_percentage"])
    def test_missing_all_evidence_is_blocked(self):
        r=summarize(None,None)
        self.assertEqual(r["history"]["status"],"CHECKPOINT_UNAVAILABLE")
        self.assertTrue(all(x["status"]=="EVIDENCE_MISSING_OR_INVALID"
                            for x in r["lanes"].values()))
        self.assertFalse(r["buy_recommendations_authorized"])
if __name__=="__main__":unittest.main()
