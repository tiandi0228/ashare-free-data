import unittest
from collector.p2_gap_recovery_plan import recovery
class RecoveryTests(unittest.TestCase):
    def test_no_bridge(self):
        rows=[{"date":"2026-10-16","tradestatus":"1"},{"date":"2026-10-19","tradestatus":"0"},{"date":"2026-10-20","tradestatus":"1"}]
        self.assertEqual(recovery(rows,"2026-10-20")["additional_consecutive_observations_needed"],20)
    def test_asof_halt(self):
        self.assertEqual(recovery([{"date":"2026-10-20","tradestatus":"0"}],"2026-10-20")["additional_consecutive_observations_needed"],21)
    def test_future_excluded(self):
        rows=[{"date":"2026-10-20","tradestatus":"1"},{"date":"2026-10-21","tradestatus":"1"}]
        self.assertEqual(recovery(rows,"2026-10-20")["trailing_tradable_observations"],1)
