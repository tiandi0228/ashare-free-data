import unittest
from collector.p3_delist_timeline import classify
from collector.p4_curated_session_exit import sessions_between
class DelistTests(unittest.TestCase):
    def setUp(self):
        self.rows=[dict(date="2026-11-12",code="sz.002731",tradestatus="1")]
        self.days=sessions_between("2026-11-13","2026-11-25")
    def test_tail(self):
        self.assertEqual(classify(self.rows,self.days,self.days),"DELISTING_TAIL_RETROSPECTIVELY_EXPLAINED")
    def test_missing_day(self):
        with self.assertRaises(ValueError):classify(self.rows,self.days[:-1],self.days)
    def test_wrong_issuer(self):
        self.rows[0]["code"]="sz.002717"
        with self.assertRaises(ValueError):classify(self.rows,self.days,self.days)
