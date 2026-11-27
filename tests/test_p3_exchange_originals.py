import unittest
from collector.p3_exchange_originals import verify
class OriginalsTests(unittest.TestCase):
    def test_normalize(self):
        self.assertTrue(verify("603595 2026－053 撤销其他风险警示 11 月 25 日",("603595","2026-053","撤销其他风险警示","11月25日")))
    def test_wrong_date(self):
        self.assertFalse(verify("603595 11月26日",("603595","11月25日")))
