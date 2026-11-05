"""An independent P1 schedule cannot circumvent the existing at-most-once guard."""
import re
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

FILE=Path(".github/workflows/p1-independent-recovery-watchdog.yml")

class IndependentRecoveryWatchdogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow=FILE.read_text(encoding="utf-8")
    def test_all_approved_weekday_and_weekend_followup_slots(self):
        self.assertEqual(re.findall(r"cron: '([^']+)'",self.workflow), [
            "32 1,2,4,6,8,10,12,14 * * 1-5",
            "32 16 * * 1-5",
            "32 18 * * 0-4",
            "32 2,8,12,16 * * 6,0",
        ])
        self.assertIn("cancel-in-progress: false",self.workflow)

    def test_each_beijing_source_slot_has_one_recovery_82_minutes_later(self):
        # Build a complete UTC week using the actual minute/hour/weekday cron
        # expressions. Exercise rollover for Monday 01:10 and Sun 23:10.
        rules=re.findall(r"cron: '([^']+)'",self.workflow)
        utc=timezone.utc
        china=ZoneInfo("Asia/Shanghai")
        start=datetime(2026,11,1,tzinfo=utc)  # Sunday
        checks=[]
        for day in range(7):
            utc_day=start+timedelta(days=day)
            for rule in rules:
                minute,hours,_,_,weekdays=rule.split()
                wd=(utc_day.weekday()+1)%7 # cron: Sun=0
                permitted=set()
                for part in weekdays.split(","):
                    if "-" in part:
                        a,b=map(int,part.split("-"))
                        permitted.update(range(a,b+1))
                    else:
                        permitted.add(int(part))
                if wd not in permitted:
                    continue
                for hour in hours.split(","):
                    instant=utc_day.replace(hour=int(hour),minute=int(minute))
                    checks.append(instant.astimezone(china))
        # The example week Sun Nov 1 through Sat Nov 7 must cover all Mon-Fri
        # 01:10,08:10,09:10,11:10,13:10,15:10,17:10,19:10,21:10,
        # 23:10 plus Sat/Sun 09:10,15:10,19:10,23:10, where the
        # recovery happens 82min after the scheduled P1 source slot.
        for day in range(2,8):  # Monday Nov 2 through Saturday Nov 7
            target=(1,8,9,11,13,15,17,19,21,23) if day<7 else (9,15,19,23)
            for hour in target:
                scheduled=datetime(2026,11,day,hour,10,tzinfo=china)
                matches=[run for run in checks
                         if run-scheduled==timedelta(minutes=82)]
                self.assertEqual(len(matches),1,(scheduled,matches))
        self.assertEqual(len(checks),66) # full UTC week; includes boundary windows

    def test_explicit_write_permission_not_pr_dispatch(self):
        self.assertIn("contents: write",self.workflow)
        self.assertIn("actions: write",self.workflow)
        self.assertIn("github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'",
                      self.workflow)
        self.assertNotIn("github.event_name == 'pull_request' ||",self.workflow)
        self.assertIn("github.event_name == 'push' && github.ref == 'refs/heads/main'",self.workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'",self.workflow)
        self.assertIn("github.event_name == 'schedule'",self.workflow)
        self.assertNotIn("github.event_name == 'pull_request' ||",self.workflow)
        self.assertIn("needs: verify",self.workflow)
    def test_existing_fail_closed_chain_required(self):
        positions=[]
        for module in ("p1_schedule_watchdog","p1_safe_recovery",
                       "p1_recovery_claim","p1_recovery_dispatch_preflight",
                       "p1_recovery_dispatch_once",
                       "p1_recovery_run_reconciliation"):
            needle="python -m collector."+module+" "
            self.assertIn(needle,self.workflow)
            positions.append(self.workflow.index(needle))
        self.assertEqual(positions,sorted(positions))
        self.assertIn("P1_RECOVERY_EXECUTION_ENABLED: 'true'",self.workflow)
        self.assertIn("--preflight evidence/p1/preflight.json",self.workflow)
        self.assertIn("p1-independent-recovery-${{ github.run_id }}",self.workflow)
    def test_no_new_orders_or_bypass(self):
        self.assertNotIn("shards_per_run: '2'",self.workflow)
        self.assertNotIn("trade_gate: OPEN",self.workflow)

if __name__=="__main__":
    unittest.main()
