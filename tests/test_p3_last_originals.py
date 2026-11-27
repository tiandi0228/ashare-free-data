import unittest
from collector.p3_last_originals import SOURCES,missing
class LastTests(unittest.TestCase):
    def test_tokens(self):
        for _,tokens,_,_,_ in SOURCES.values():self.assertEqual(missing(" ".join(tokens),tokens),[])
    def test_wrong_notice(self):
        t=SOURCES["sz.002122"][1]
        self.assertIn("2026-051",missing(" ".join(t).replace("2026-051","2026-050"),t))
    def test_wrong_limit(self):
        t=SOURCES["sz.000892"][1]
        self.assertIn("仍为10%",missing(" ".join(t).replace("10%","5%"),t))
