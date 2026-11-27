import unittest
from collector.p3_additional_originals import verify,SOURCES
class AdditionalTests(unittest.TestCase):
    def test_all_tokens(self):
        tokens=SOURCES["sz.000820"][1]
        self.assertEqual(verify(" ".join(tokens),tokens),[])
    def test_wrong_band(self):
        tokens=SOURCES["sz.000820"][1]
        self.assertEqual(verify(" ".join(tokens).replace("10%","5%"),tokens),["10%"])
    def test_wrong_notice(self):
        tokens=SOURCES["sh.600567"][1]
        self.assertIn("2026-075",verify(" ".join(tokens).replace("2026-075","2026-076"),tokens))
