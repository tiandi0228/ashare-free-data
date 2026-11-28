import unittest
from collector.p3_resume_originals import days,verify,SOURCES
class ResumeTests(unittest.TestCase):
    def test_intervals(self):
        self.assertEqual(len(days("2026-10-21","2026-11-04")),10)
        self.assertEqual(len(days("2026-11-02","2026-11-16")),10)
        self.assertEqual(days("2026-11-23","2026-11-24"),["2026-11-23"])
    def test_identity(self):
        for _,tokens,_,_,_ in SOURCES.values():self.assertEqual(verify(" ".join(tokens),tokens),[])
    def test_limit(self):
        t=SOURCES["sz.002872"][1]
        self.assertIn("日涨跌幅限制仍为10%",verify(" ".join(t).replace("10%","5%"),t))
