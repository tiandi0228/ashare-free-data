import unittest
from collector.p3_interval_extension import verify,TOKENS
class ExtensionTests(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(verify(" ".join(TOKENS)))
    def test_wrong_resume(self):
        self.assertFalse(verify(" ".join(TOKENS).replace("2026年11月2日","2026年11月3日")))
    def test_wrong_notice(self):
        self.assertFalse(verify(" ".join(TOKENS).replace("2026-060","2026-061")))
