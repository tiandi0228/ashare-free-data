import unittest
from unittest.mock import patch
from collector.p2_original_gap_window_triage import classify,diagnose,check_current_checkpoint

def row(date,status="1"):
    return {"date":date,"tradestatus":status}

class GapSourceTests(unittest.TestCase):
    def test_fewer_21_vendor_rows_is_not_an_official_listing_date(self):
        sample=[row("2026-10-20"),row("2026-10-21"),row("2026-10-22")]
        x=classify(sample,asof="2026-10-22")
        self.assertEqual(x["diagnosis"],"FEWER_THAN_21_VENDOR_ROWS_ASOF")
        self.assertFalse(x["official_halt_explanation_authenticated"])
        self.assertFalse(x["vendor_row_window_is_calendar_coverage"])

    def test_suspended_vendor_row_in_last_21_must_not_be_bridged(self):
        rows=[row(f"2026-10-{i:02d}",status="0" if i==10 else "1")
              for i in range(2,23)]
        x=classify(rows,asof="2026-10-22")
        self.assertEqual(x["diagnosis"],"VENDOR_SUSPENDED_ROW_WITHIN_LAST_21")
        self.assertEqual(x["trailing_vendor_suspended_rows"],1)

    def test_unordered_duplicate_or_unknown_vendor_rows_fail_closed(self):
        asof="2026-10-22"
        valid=[row("2026-10-20"),row("2026-10-21","0"),row(asof)]
        with self.assertRaisesRegex(ValueError,"unordered"):
            classify([valid[1],valid[0],valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"duplicate"):
            classify([valid[0],valid[1],valid[1],valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"trade status"):
            classify([valid[0],row("2026-10-21","UNKNOWN"),valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"row date"):
            classify([valid[0],row("2026-02-30"),valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"as-of"):
            classify(valid,asof="2026-02-30")
        # A later original vendor row must not be silently used to fill an
        # earlier as-of research window.
        result=classify(valid+[row("2026-10-23")],asof=asof)
        self.assertEqual(result["available_vendor_rows_through_asof"],3)
        self.assertFalse(result["official_halt_explanation_authenticated"])

    def test_current_checkpoint_coverage_matching_and_growth_fail_closed(self):
        epoch="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
        checkpoint={"source_sha256":epoch,"completed_shards":2,
                    "completed_issuers":16,
                    "completed":[{"index":6},{"index":7}]}
        status={"source_sha256":epoch,"trade_gate":"BLOCKED","archived_shards":[6,7]}
        coverage={"phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
                  "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
                  "source_epoch_sha256":epoch,"trade_gate":"BLOCKED","orders":[],
                  "historical_PIT_verified":False,
                  "coverage_certified_for_trading":False,
                  "full_archive_evidence_accounted":True,
                  "unobserved_archived_shards":0,"unobserved_issuer_count":0,
                  "checkpoint_completed_shards":2,
                  "archived_original_shards":2,"observed_archived_shards":2,
                  "observed_feature_or_gap_issuers":16,
                  "observed_shard_ids":["shard_0006","shard_0007"],
                  "issuer_evidence_gap_count":1}
        with patch("collector.p1_checkpoint.validate",return_value=None):
            result=check_current_checkpoint(coverage,checkpoint,status)
            self.assertEqual(result["checkpoint_completed_shards"],2)
            self.assertEqual(result["gap_issuer_count"],1)
            self.assertEqual(result["trade_gate"],"BLOCKED")
            checkpoint["completed_shards"]=3
            checkpoint["completed"].append({"index":8})
            checkpoint["completed_issuers"]=24
            status["archived_shards"].append(8)
            with self.assertRaisesRegex(ValueError,"stale"):
                check_current_checkpoint(coverage,checkpoint,status)
            checkpoint["completed_shards"]=2
            checkpoint["completed"].pop()
            checkpoint["completed_issuers"]=16
            status["archived_shards"].pop()
            coverage["observed_shard_ids"].append("shard_0007")
            with self.assertRaisesRegex(ValueError,"stale"):
                check_current_checkpoint(coverage,checkpoint,status)

    def test_current_checkpoint_rejects_vendor_pit_promotion_and_missing_shard(self):
        epoch="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
        checkpoint={"source_sha256":epoch,"completed_shards":1,
                    "completed_issuers":8,"completed":[{"index":6}]}
        status={"source_sha256":epoch,"trade_gate":"BLOCKED","archived_shards":[6]}
        base={"phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
              "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
              "source_epoch_sha256":epoch,"trade_gate":"BLOCKED","orders":[],
              "historical_PIT_verified":False,"coverage_certified_for_trading":False,
              "full_archive_evidence_accounted":True,
              "unobserved_archived_shards":0,"unobserved_issuer_count":0,
              "checkpoint_completed_shards":1,"archived_original_shards":1,
              "observed_archived_shards":1,"observed_feature_or_gap_issuers":8,
              "observed_shard_ids":["shard_0006"],"issuer_evidence_gap_count":1}
        with patch("collector.p1_checkpoint.validate",return_value=None):
            for key,value in (("trade_gate","OPEN"),
                              ("historical_PIT_verified",True),
                              ("coverage_certified_for_trading",True),
                              ("full_archive_evidence_accounted",False),
                              ("unobserved_archived_shards",1)):
                changed=dict(base,key="dummy")
                changed.pop("key")
                changed[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):
                    check_current_checkpoint(changed,checkpoint,status)
            with self.assertRaises(ValueError):
                check_current_checkpoint(base,checkpoint,
                    dict(status,archived_shards=[7]))
            with self.assertRaises(ValueError):
                check_current_checkpoint(base,checkpoint,
                    dict(status,archived_shards=[]))

    def test_complete_window_not_a_gap_and_no_source_fabrication(self):
        rows=[row(f"2026-10-{i:02d}") for i in range(2,23)]
        with self.assertRaises(ValueError):classify(rows,asof="2026-10-22")
        with self.assertRaises(ValueError):classify(rows[:-1],asof="2026-10-22")
        with self.assertRaises(ValueError):diagnose({},'.')

if __name__=="__main__":unittest.main()
