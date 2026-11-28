import unittest
from collector.p3_final_gap_leads import LEADS,PDFS,missing
class FinalGapTests(unittest.TestCase):
    def test_scope(self):
        self.assertEqual(len(LEADS),6)
        self.assertEqual(len(PDFS),2)
        self.assertTrue(set(PDFS)<=set(LEADS))
    def test_identity(self):
        for _,tokens,_ in PDFS.values():self.assertEqual(missing(" ".join(tokens),tokens),[])
    def test_wrong_notice(self):
        _,tokens,_=PDFS["sz.000635"]
        self.assertIn("2026-065",missing(" ".join(tokens).replace("2026-065","2026-063"),tokens))
