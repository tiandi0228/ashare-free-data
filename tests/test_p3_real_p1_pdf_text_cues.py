import unittest
from unittest.mock import patch
from collector.p3_real_p1_pdf_text_cues import extract
class CuesTest(unittest.TestCase):
    def test_extraction_never_certifies_effectiveness(self):
        import tempfile,json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/"quality.json").write_text(json.dumps({"sources":[{"issuer":"sz.000001","announcement_id":"123","original_bytes_verified":False}]}))
            with patch("collector.p3_real_p1_pdf_text_cues.audit",return_value={"independently_sha_verified":0}):
                r=extract(p)
            self.assertEqual(r["event_effective_dates_certified"],0)
            self.assertEqual(r["sources"][0]["date_contexts_research_only"] if "date_contexts_research_only" in r["sources"][0] else [],[])
            self.assertEqual(r["sources"][0]["text_status"],"UNAVAILABLE_NOT_NO_RISK")

    def test_truncated_sha_verified_pdf_is_quarantined_not_certified(self):
        import tempfile,json
        from pathlib import Path
        from pypdf.errors import PdfReadError
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/"original.pdf").write_bytes(b"%PDF-1.7\nnot a complete pdf")
            rows=[
                {"issuer":"sh.600001","announcement_id":"100",
                 "original_bytes_verified":True,"original_file":"original.pdf",
                 "sha256":"a"*64},
                {"issuer":"sz.000001","announcement_id":"101",
                 "original_bytes_verified":False,"sha256":None}
            ]
            (p/"quality.json").write_text(json.dumps({"sources":rows}))
            with patch("collector.p3_real_p1_pdf_text_cues.audit",
                       return_value={"independently_sha_verified":1}), \
                 patch("collector.p3_real_p1_pdf_text_cues.PdfReader",
                       side_effect=PdfReadError("EOF marker not found")):
                r=extract(p)
            self.assertEqual(r["source_count"],2)
            self.assertEqual(r["quarantined_pdf_parse_failures"],1)
            failed=r["sources"][0]
            self.assertEqual(failed["text_status"],"PDF_PARSE_FAILED_UNVERIFIED")
            self.assertEqual(failed["parse_failure_category"],"PdfReadError")
            self.assertEqual(failed["date_contexts_research_only"],[])
            self.assertEqual(failed["original_sha256"],"a"*64)
            self.assertTrue(failed["requires_original_refetch_or_manual_review"])
            self.assertFalse(failed["historical_PIT_verified"])
            self.assertFalse(r["historical_PIT_verified"])
            self.assertEqual(r["trade_gate"],"BLOCKED")
            self.assertEqual(r["orders"],[])
            self.assertEqual(r["sources"][1]["text_status"],"UNAVAILABLE_NOT_NO_RISK")

    def test_integrity_audit_failure_never_quarantined(self):
        import tempfile,json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            (p/"quality.json").write_text(json.dumps({"sources":[]}))
            with patch("collector.p3_real_p1_pdf_text_cues.audit",
                       side_effect=ValueError("SHA mismatch")):
                with self.assertRaisesRegex(ValueError,"SHA mismatch"):
                    extract(p)
if __name__=="__main__":unittest.main()
