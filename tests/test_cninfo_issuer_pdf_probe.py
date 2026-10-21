"""Offline PDF source boundary tests: no GitHub runner network required."""
import json
import tempfile
import unittest
from pathlib import Path
from collector.cninfo_issuer_pdf_probe import URL, capture, inspect_pdf, MAX_BYTES

TEXT = ("湖北华嵘控股股份有限公司 证券代码：600421 "
        "关于公司股票进入退市整理期的风险提示公告 "
        "退市整理期 预计最后交易日期为2026 年6 月22 日")


class PDFProofTests(unittest.TestCase):
    def test_notice_is_expected_trading_day_not_final_exchange_delist_date(self):
        with tempfile.TemporaryDirectory() as root:
            attempts = []
            def getter(url):
                attempts.append(url)
                return b"%PDF-FAKE-TEXT-FIXTURE", url
            self.assertEqual(capture(root, getter, lambda _: (TEXT, 2)), 0)
            self.assertEqual(attempts, [URL])
            q = json.loads((Path(root) / "quality.json").read_text())
            self.assertEqual(q["risk_notice_expected_last_trading_date"], "2026-06-22")
            self.assertFalse(q["actual_exchange_delist_effective_date_verified_from_this_pdf"])
            self.assertFalse(q["historical_asof_publication_timestamp_verified"])
            self.assertFalse(q["exchange_publisher_identity_signed"])
            self.assertEqual(q["trade_gate"], "BLOCKED")
            self.assertEqual(q["orders"], [])

    def test_missing_identity_or_notice_date_blocks(self):
        with self.assertRaisesRegex(ValueError, "anchors absent"):
            inspect_pdf(b"%PDF-fake", URL, "600421退市整理期", 1)

    def test_wrong_redirect_blocks(self):
        with self.assertRaisesRegex(ValueError, "URL mismatch"):
            inspect_pdf(b"%PDF-fake", "https://another.example/b.pdf", TEXT, 2)

    def test_bot_challenge_or_byte_budget_blocks(self):
        with self.assertRaisesRegex(ValueError, "bounded PDF"):
            inspect_pdf(b"<html>denied</html>", URL, TEXT, 2)
        with self.assertRaisesRegex(ValueError, "bounded PDF"):
            inspect_pdf(b"%PDF-" + b"x" * MAX_BYTES, URL, TEXT, 2)

    def test_failed_network_does_not_become_verified(self):
        with tempfile.TemporaryDirectory() as root:
            def denied(url):
                raise OSError("source not reachable")
            self.assertEqual(capture(root, denied), 2)
            q = json.loads((Path(root) / "quality.json").read_text())
            self.assertEqual(q["attempted_gets"], 1)
            self.assertEqual(q["failure_type"], "OSError")
            self.assertEqual(q["status"], "BLOCKED_NO_SOURCE")
            self.assertEqual(q["orders"], [])


if __name__ == "__main__":
    unittest.main()
