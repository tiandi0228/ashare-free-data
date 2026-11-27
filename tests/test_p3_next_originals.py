import unittest
from collector.p3_next_originals import missing,SOURCES
class NextTests(unittest.TestCase):
    def test_identity(self):
        for _,tokens,_,_ in SOURCES.values():self.assertEqual(missing(" ".join(tokens),tokens),[])
    def test_wrong_notice(self):
        tokens=SOURCES["sh.603580"][1]
        self.assertIn("2026-080",missing(" ".join(tokens).replace("2026-080","2026-081"),tokens))
    def test_initial_only(self):
        self.assertEqual(SOURCES["sh.605258"][3],"INITIAL_HALT_ONLY")
