"""Offline tests of recovery policy: no historical P1 dispatch performed."""
import datetime as dt,unittest
from zoneinfo import ZoneInfo
from collector.p1_safe_recovery import eligibility
TZ=ZoneInfo("Asia/Shanghai")
def tm(h,m):
    return dt.datetime(2026,11,3,h,m,tzinfo=TZ)
def run(id,h,m,event="schedule",status="completed",conclusion="success"):
    return {"id":id,"event":event,"status":status,"conclusion":conclusion,
        "created_at":tm(h,m).astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"),
        "path":".github/workflows/p1-fresh-vendor-roster.yml"}

class RecoveryPolicyTests(unittest.TestCase):
    def test_mature_missing_slot_review_only(self):
        r=eligibility(tm(14,20),[run(1,11,12)],total_count=1)
        self.assertEqual(r["state"],"ELIGIBLE_FOR_SINGLE_SHARD_RECOVERY_REVIEW")
        self.assertEqual(r["requested_shards"],1)
        self.assertFalse(r["auto_dispatched"])
        self.assertFalse(r["auto_dispatch_enabled"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
    def test_existing_scheduled_run_blocks(self):
        r=eligibility(tm(14,20),[run(1,11,12),run(2,13,20)],total_count=2)
        self.assertEqual(r["reason"],"SCHEDULE_SLOT_NOT_MISSING")
    def test_running_historical_blocks(self):
        r=eligibility(tm(14,20),[run(1,11,12),
                         run(2,12,5,event="workflow_dispatch",status="in_progress",
                             conclusion=None)],total_count=2)
        self.assertEqual(r["reason"],"P1_RUN_ACTIVE")
    def test_manual_or_push_run_after_slot_blocks(self):
        for kind in ("push","workflow_dispatch"):
            with self.subTest(event=kind):
                r=eligibility(tm(14,20),[run(1,11,12),run(3,13,25,event=kind)],
                              total_count=2)
                self.assertEqual(r["reason"],"P1_RUN_ALREADY_STARTED_AFTER_SLOT")
    def test_grace_and_stale_windows_block(self):
        self.assertEqual(eligibility(tm(14,0),[run(1,11,12)],total_count=1)["reason"],
                         "OUTSIDE_SAFE_RECOVERY_WINDOW")
        self.assertEqual(eligibility(tm(14,45),[run(1,11,12)],total_count=1)["reason"],
                         "OUTSIDE_SAFE_RECOVERY_WINDOW")
    def test_run_list_not_covering_slot_blocks(self):
        r=eligibility(tm(14,20),[run(2,13,50,event="push")],total_count=100)
        self.assertEqual(r["reason"],"RUN_HISTORY_DOES_NOT_COVER_SLOT")
    def test_failed_recent_collection_blocks_duplicate(self):
        r=eligibility(tm(14,20),[run(1,11,12),
                   run(2,13,30,event="workflow_dispatch",conclusion="failure")],
                   total_count=2)
        self.assertEqual(r["reason"],"P1_RUN_ALREADY_STARTED_AFTER_SLOT")
    def test_mismatched_actual_cron_prevents_unsafe_recovery(self):
        delayed=run(3,13,20)
        delayed["display_title"]="P1 origin 10 1 * * 1-5 [NO TRADES]"
        result=eligibility(tm(14,20),[run(1,11,12),delayed],total_count=2)
        self.assertEqual(result["reason"],"SCHEDULE_SLOT_NOT_MISSING")
        self.assertFalse(result["auto_dispatched"])

    def test_malformed_or_missing_github_data_blocks(self):
        self.assertEqual(eligibility(tm(14,20),[],total_count=0)["reason"],
                         "RUN_COVERAGE_UNVERIFIED")
        self.assertEqual(eligibility(tm(14,20),[run(1,11,12)],total_count=0)["reason"],
                         "RUN_LIST_TRUNCATED_OR_INVALID")
        malformed=run(1,11,12);malformed["created_at"]="not-a-date"
        self.assertEqual(eligibility(tm(14,20),[malformed],total_count=1)["reason"],
                         "MALFORMED_RUN_TIMESTAMP")
if __name__=="__main__":unittest.main()
