import unittest,hashlib
from collector.p3_unified_ledger import verified_pdf,index_tasks
class LedgerTests(unittest.TestCase):
    def test_valid_bytes(self):
        b=b"%PDF-test";verified_pdf(b,hashlib.sha256(b).hexdigest())
    def test_tamper(self):
        with self.assertRaises(ValueError):verified_pdf(b"%PDF-tamper","0"*64)
    def test_html(self):
        b=b"<html>"
        with self.assertRaises(ValueError):verified_pdf(b,hashlib.sha256(b).hexdigest())
    def test_duplicate_issuer(self):
        q=dict(asof="2026-11-25",trade_gate="BLOCKED",orders=[],executable_candidates=[],official_certified=0,historical_PIT_verified=False,tasks=[dict(issuer="sz.000635")]*19)
        with self.assertRaises(ValueError):index_tasks(q)
