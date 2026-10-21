"""Safe issuer notice date and original-source fail-closed contracts."""
import json
import tempfile
import unittest
from pathlib import Path
from collector.cninfo_early_risk_probe import URL, verify, run

TEXT=("湖北华嵘控股股份有限公司 600421 关于公司股票进入退市整理期交易的公告 "
      "退市整理期交易起始日为2026年6月1日；预计最后交易日期为2026年6月22日")

class EarlyNoticeTests(unittest.TestCase):
    def test_source_notice_preserves_non_actionable_future_resume(self):
        with tempfile.TemporaryDirectory() as root:
            calls=[]
            def fake_fetch(url):
                calls.append(url)
                return b"%PDF-mock-earlier-event-document", url
            self.assertEqual(run(root,fake_fetch,lambda raw:(TEXT,2)),0)
            self.assertEqual(calls,[URL])
            q=json.loads((Path(root)/"quality.json").read_text())
            self.assertEqual(q["issuer_stated_resumption_date"],"2026-06-01")
            self.assertFalse(q["tradability_on_resumption_date_exchange_verified"])
            self.assertFalse(q["historical_asof_certified"])
            self.assertFalse(q["original_issuer_publication_instant_verified"])
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertEqual(q["orders"],[])
    def test_redirect_wrong_original_url_refused(self):
        with self.assertRaisesRegex(ValueError,"source URL"):
            verify(b"%PDF-mock","https://other.invalid/source",TEXT,2)
    def test_unrelated_pdf_rejected(self):
        with self.assertRaisesRegex(ValueError,"Missing anchored"):
            verify(b"%PDF-mock",URL,"600421",2)
    def test_html_and_oversized_pdf_rejected(self):
        with self.assertRaisesRegex(ValueError,"PDF header"):
            verify(b"<html>error</html>",URL,TEXT,2)
    def test_error_keeps_gate_closed(self):
        with tempfile.TemporaryDirectory() as root:
            def denied(url):
                raise OSError("blocked")
            self.assertEqual(run(root,denied),2)
            q=json.loads((Path(root)/"quality.json").read_text())
            self.assertEqual(q["status"],"BLOCKED_NO_SOURCE")
            self.assertEqual(q["failure_type"],"OSError")
            self.assertEqual(q["attempted_https_gets"],1)
            self.assertEqual(q["orders"],[])
if __name__=="__main__":
    unittest.main()
