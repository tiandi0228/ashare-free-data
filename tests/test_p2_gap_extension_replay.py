import unittest
from collector.p2_gap_extension_replay import inspect
from collector.p2_independent_bars import FIELDS

def raw(days):
    return (",".join(FIELDS)+"\n"+"".join(f"{day},sh.600150,10,10,10,10,100,1000,3,{status}\n" for day,status in days)).encode()

class ExtensionTests(unittest.TestCase):
    def test_gap_not_rewritten(self):
        a=raw([("2026-10-20","0")])
        b=raw([("2026-11-25","1")])
        r=inspect(a,b,"sh.600150")
        self.assertEqual(r["additional_consecutive_observations_needed"],20)
        self.assertFalse(r["historical_gap_resolved"])
        self.assertFalse(r["recovered_at_new_cutoff"])
    def test_overlap_or_wrong_cutoff_rejected(self):
        with self.assertRaises(ValueError):
            inspect(raw([("2026-10-20","1")]),raw([("2026-10-20","1")]),"sh.600150")

    def test_complete_calendar_and_actual_features(self):
        from collector.p4_curated_session_exit import sessions_between
        days=sessions_between("2026-10-21","2026-11-25")
        a=raw([("2026-10-20","0")])
        b=raw([(d,"1") for d in days])
        r=inspect(a,b,"sh.600150")
        self.assertTrue(r["recovered_at_new_cutoff"])
        self.assertEqual(r["research_features"]["ma20_close_cny"],"10.0000")
        self.assertEqual(r["missing_expected_sessions"],[])
    def test_missing_session_blocks_even_with_21_rows(self):
        from collector.p4_curated_session_exit import sessions_between
        days=sessions_between("2026-10-21","2026-11-25")
        a=raw([("2026-10-20","0")])
        b=raw([(d,"1") for d in days[1:]])
        r=inspect(a,b,"sh.600150")
        self.assertFalse(r["recovered_at_new_cutoff"])
        self.assertEqual(r["missing_expected_sessions"],[days[0]])
        self.assertIsNone(r["research_features"])
