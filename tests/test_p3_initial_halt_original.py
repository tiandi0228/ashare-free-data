import unittest
from collector.p3_initial_halt_original import verify
class HaltTests(unittest.TestCase):
    def test_identity(self):
        self.assertTrue(verify("600185 2026－073 重大资产重组 停牌 2026 年 11 月 12 日"))
    def test_wrong_day(self):
        self.assertFalse(verify("600185 2026-073 重大资产重组 停牌 2026年11月13日"))
