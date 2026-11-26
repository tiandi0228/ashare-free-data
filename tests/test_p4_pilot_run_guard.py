import unittest
from datetime import datetime, timezone
from collector.p4_pilot_run_guard import verify, REPO

NOW = datetime(2026,12,1,11,40,tzinfo=timezone.utc)
DAY = "2026-12-01"
RUN = dict(id=12,head_branch="main",event="schedule",repository={"full_name":REPO},created_at="2026-12-01T11:39:00Z")
EMPTY = dict(total_count=0,artifacts=[])

class RunGuardTests(unittest.TestCase):
    def test_new_day_and_duplicate(self):
        self.assertTrue(verify(NOW,DAY,12,RUN,EMPTY)["allowed"])
        r=verify(NOW,DAY,12,RUN,dict(total_count=1,artifacts=[{"name":"p4-prospective-"+DAY}]))
        self.assertFalse(r["allowed"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])

    def test_cross_day_future_and_wrong_run_rejected(self):
        for change in (dict(created_at="2026-11-30T11:39:00Z"),dict(created_at="2026-12-01T11:41:00Z"),dict(id=13),dict(event="pull_request"),dict(head_branch="other")):
            with self.assertRaises(ValueError):
                verify(NOW,DAY,12,dict(RUN,**change),EMPTY)

    def test_incomplete_and_unexpected_inventory_rejected(self):
        for a in (dict(total_count=1,artifacts=[]),dict(total_count=1,artifacts=[{"name":"other"}]),dict(total_count=False,artifacts=[])):
            with self.assertRaises(ValueError):
                verify(NOW,DAY,12,RUN,a)
