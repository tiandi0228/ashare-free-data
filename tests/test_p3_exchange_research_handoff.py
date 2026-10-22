import copy,json,unittest
from pathlib import Path
from collector.p3_exchange_research_handoff import assemble
from collector.p3_exchange_notice_event_reconciliation import reconcile
from collector.p3_typed_event_research_ledger import normalize
from collector.p3_two_pdf_event_chain import combine
class ExchangeResearchHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]/"reports"
        load=lambda n:json.loads((root/n).read_text())
        cls.ledger=normalize(combine(load("p3_cninfo_600421_early_20261021.json"),load("p3_cninfo_600421_disclosure_pdf_20261021.json"),"2026-06-22"))
        cls.exchange=reconcile(load("p3_600421_two_pdf_event_chain_20261021.json"),
          load("p3_sse_two_official_original_sha_observed_20261022.json"),
          load("p3_cninfo_two_pdf_independent_sha_recapture_20261022.json"),
          load("p3_sse_independent_two_originals_verified_20261022.json"))
    def test_real_notice_and_issuer_ledger_still_no_PIT(self):
        x=assemble(self.ledger,self.exchange)
        self.assertEqual(x["observed_exchange_effective_date_notices"],1)
        self.assertEqual(x["historically_authenticated_effective_dates"],0)
        self.assertEqual(x["trade_gate"],"BLOCKED")
    def test_forged_historical_publication_rejected(self):
        e=copy.deepcopy(self.exchange)
        e["rows"][0]["historical_asof_publication_verified"]=True
        with self.assertRaises(ValueError):assemble(self.ledger,e)
    def test_wrong_issuer_rejected(self):
        e=copy.deepcopy(self.exchange);e["rows"][0]["issuer"]="sh.600000"
        with self.assertRaises(ValueError):assemble(self.ledger,e)
if __name__=="__main__":unittest.main()
