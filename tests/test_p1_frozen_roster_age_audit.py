"""P1 frozen roster age guard: tests must not contact Baostock or trade."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo

from collector.p1_frozen_roster_age_audit import inspect
from collector.p1_roster_lock import pack
from tests.test_p1_roster_lock import RosterLockTests

TZ = ZoneInfo("Asia/Shanghai")


class FrozenRosterAgeTests(unittest.TestCase):
    def setUp(self):
        fixture=RosterLockTests("test_pack_and_unpack")
        self.fixture=fixture

    def sample(self):
        # Use the actual existing roster test fixture for well-formed SHA bytes.
        from tests.test_p1_roster_lock import sample
        raw, receipt = sample()
        return pack(raw, receipt, 1234)

    def test_three_week_old_snapshot_never_becomes_live(self):
        lock=self.sample()
        original=lock["original_quality"]["requested_day"]
        now=dt.datetime.fromisoformat(original).replace(tzinfo=TZ)+dt.timedelta(days=21)
        report=inspect(lock,now)
        self.assertEqual(report["source_age_calendar_days"],21)
        self.assertEqual(report["roster_freshness_status"],"HISTORICAL_FROZEN_SNAPSHOT_NOT_CURRENT")
        self.assertFalse(report["buy_recommendations_authorized"])
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])

    def test_same_day_still_not_authenticated_current(self):
        lock=self.sample()
        day=lock["original_quality"]["requested_day"]
        report=inspect(lock,dt.datetime.fromisoformat(day).replace(tzinfo=TZ))
        self.assertEqual(report["source_age_calendar_days"],0)
        self.assertFalse(report["current_day_roster_authenticated"])
        self.assertEqual(report["roster_freshness_status"],"SAME_DAY_UNVERIFIED_NOT_LIVE_AUTHENTICATED")

    def test_future_and_naive_time_rejected(self):
        lock=self.sample()
        day=dt.date.fromisoformat(lock["original_quality"]["requested_day"])
        with self.assertRaises(ValueError):
            inspect(lock,dt.datetime.combine(day,dt.time(0,0)))
        with self.assertRaises(ValueError):
            inspect(lock,dt.datetime.combine(day-dt.timedelta(days=1),dt.time(23,0),TZ))

    def test_tampered_sha_receipt_rejected(self):
        lock=self.sample()
        lock["source_sha256"]="0"*64
        with self.assertRaises(ValueError):
            inspect(lock,dt.datetime.now(TZ))


if __name__=="__main__":
    unittest.main()
