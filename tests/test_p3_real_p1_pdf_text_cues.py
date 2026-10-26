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
if __name__=="__main__":unittest.main()
