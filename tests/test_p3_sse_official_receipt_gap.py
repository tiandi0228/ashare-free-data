"""Real SSE official event pages do not certify complete historical PIT state."""
import copy,json,unittest
from pathlib import Path
from collector.p3_sse_official_receipt_gap import reconcile
REPORT=Path(__file__).resolve().parents[1]/"reports/p3_sse_two_official_original_sha_observed_20261022.json"

class SSEReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q=json.loads(REPORT.read_text("utf-8"))
    def test_real_two_official_pages_still_leave_28_cells(self):
        r=reconcile(self.q)
        self.assertEqual(r["official_host_pages_observed"],2)
        self.assertEqual((r["verified_evidence_cells"],r["missing_evidence_cells"]),(0,28))
        self.assertEqual(r["official_announcement_effective_delist_date"],"2026-06-26")
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_forged_effective_day_fails(self):
        q=copy.deepcopy(self.q);q["pages"][1]["effective_delist_date"]="2026-06-22"
        with self.assertRaisesRegex(ValueError,"changed"):reconcile(q)
    def test_forged_source_digest_fails(self):
        q=copy.deepcopy(self.q);q["pages"][0]["sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"changed"):reconcile(q)
    def test_forged_pit_instant_fails(self):
        q=copy.deepcopy(self.q);q["historical_intraday_publication_verified"]=True
        with self.assertRaisesRegex(ValueError,"safety gate"):reconcile(q)
    def test_new_trade_order_fails(self):
        q=copy.deepcopy(self.q);q["orders"]=[{"code":"600421"}]
        with self.assertRaisesRegex(ValueError,"safety gate"):reconcile(q)
