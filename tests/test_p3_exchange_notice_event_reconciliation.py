import copy,json,unittest
from pathlib import Path
from collector.p3_exchange_notice_event_reconciliation import reconcile
class ExchangeNoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names=("p3_600421_two_pdf_event_chain_20261021.json",
          "p3_sse_two_official_original_sha_observed_20261022.json",
          "p3_cninfo_two_pdf_independent_sha_recapture_20261022.json",
          "p3_sse_independent_two_originals_verified_20261022.json")
        cls.docs=[json.loads((Path(__file__).resolve().parents[1]/"reports"/n).read_text()) for n in names]
    def test_real_exchange_notice_date_without_pit_release(self):
        r=reconcile(*self.docs)
        self.assertEqual(r["observed_official_notice_event_count"],1)
        row=r["rows"][0]
        self.assertEqual(row["effective_date_as_stated_in_observed_official_notice"],"2026-06-26")
        self.assertEqual(row["issuer_forecast_final_trading_date"],"2026-06-22")
        self.assertIsNone(row["historically_available_at_notice_date"])
        self.assertFalse(row["usable_for_PIT_backtest"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_forged_sse_effective_date_rejected(self):
        docs=copy.deepcopy(self.docs)
        docs[1]["pages"][1]["effective_delist_date"]="2026-06-22"
        with self.assertRaises(ValueError):reconcile(*docs)
    def test_changed_sse_original_hash_rejected(self):
        docs=copy.deepcopy(self.docs)
        docs[1]["pages"][1]["sha256"]="0"*64
        with self.assertRaises(ValueError):reconcile(*docs)
if __name__=="__main__":unittest.main()
