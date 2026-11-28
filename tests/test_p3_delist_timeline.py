import unittest
from collector.p3_delist_timeline import classify, remaining_queue
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

    def test_remaining_queue(self):
        tasks={str(i):dict(extension_sha256=str(i),vendor_nontradable_days=["2026-11-25"]) for i in range(19)}
        rows=remaining_queue(tasks,{str(i) for i in range(17)})
        self.assertEqual([r["issuer"] for r in rows],["17","18"])
        self.assertTrue(all(r["official_certified"] is False for r in rows))
        self.assertEqual(rows[0]["extension_sha256"],"17")
    def test_remaining_queue_rejects_scope(self):
        tasks={str(i):{} for i in range(19)}
        with self.assertRaises(ValueError):remaining_queue(tasks,{str(i) for i in range(16)})
        with self.assertRaises(ValueError):remaining_queue(tasks,{str(i) for i in range(16)}|{"outside"})
