"""Offline chronology and source classification tests for P1 schedule watchdog."""
import datetime as dt,unittest
from zoneinfo import ZoneInfo
from collector.p1_schedule_watchdog import audit,slots

TZ=ZoneInfo("Asia/Shanghai")
def now(hour,minute=35,day=3):
    return dt.datetime(2026,11,day,hour,minute,tzinfo=TZ)
def run(run_id,when,event="schedule",status="completed",conclusion="success"):
    return dict(id=run_id,event=event,status=status,conclusion=conclusion,
                path=".github/workflows/p1-fresh-vendor-roster.yml",
                created_at=when.astimezone(dt.timezone.utc).isoformat().replace("+00:00","Z"))

class WatchdogTests(unittest.TestCase):
    def test_due_slot_matures_after_grace(self):
        self.assertEqual(slots(now(13,35))[0].strftime("%H:%M"),"11:10")
        self.assertEqual(slots(now(14,5))[0].strftime("%H:%M"),"13:10")
        self.assertEqual(slots(now(15,20))[0].strftime("%H:%M"),"13:10")
    def test_missing_schedule_not_masked_by_successful_push(self):
        r=audit(now(14,5),[run(1,now(13,12),event="push")])
        self.assertEqual(r["state"],"SUSPECTED_MISSED_SCHEDULE")
        self.assertIsNone(r["matched_schedule_run_id"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertTrue(r["no_automatic_dispatch"])
    def test_scheduled_success_matches_due_window(self):
        r=audit(now(14,5),[run(12,now(13,20))])
        self.assertEqual(r["state"],"SCHEDULE_RUN_COMPLETED")
        self.assertEqual(r["matched_schedule_run_id"],12)
    def test_failure_and_in_progress_distinguished(self):
        self.assertEqual(audit(now(14,5),[
            run(12,now(13,20),conclusion="failure")])["state"],
            "SCHEDULE_RUN_FAILED_OR_CANCELLED")
        self.assertEqual(audit(now(14,5),[
            run(13,now(13,20),status="in_progress",conclusion=None)])["state"],
            "SCHEDULE_RUN_IN_PROGRESS")
    def test_wrong_workflow_and_previous_slot_not_accepted(self):
        old=run(1,now(11,10))
        other=run(2,now(13,20))
        other["path"]=".github/workflows/p1-public-intraday-snapshot.yml"
        self.assertEqual(audit(now(14,5),[old,other])["state"],
                         "SUSPECTED_MISSED_SCHEDULE")
    def test_weekend_slots(self):
        saturday=now(20,0,day=7)
        self.assertEqual(slots(saturday)[0].strftime("%H:%M"),"19:10")
        self.assertEqual(slots(saturday)[0].weekday(),5)
    def test_unknown_input_not_success(self):
        with self.assertRaises(ValueError):audit(now(14,5),None)
        with self.assertRaises(ValueError):slots(dt.datetime(2026,11,3,14,5))

if __name__=="__main__":unittest.main()
