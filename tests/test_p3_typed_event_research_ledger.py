import copy
import json
import unittest
from pathlib import Path
from collector.p3_two_pdf_event_chain import combine
from collector.p3_typed_event_research_ledger import normalize

class TypedEventResearchLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]/"reports"
        e=json.loads((root/"p3_cninfo_600421_early_20261021.json").read_text())
        l=json.loads((root/"p3_cninfo_600421_disclosure_pdf_20261021.json").read_text())
        cls.chain=combine(e,l,"2026-06-22")

    def test_real_events_remain_not_tradable(self):
        r=normalize(self.chain)
        self.assertEqual(r["row_count"],3)
        self.assertEqual(r["confirmed_exchange_effective_event_count"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertTrue(all(e["confirmed_effective_date"] is None for e in r["rows"]))
        self.assertEqual([e["date_semantics"] for e in r["rows"]],
                         ["ISSUER_STATEMENT","ISSUER_FORECAST","UNVERIFIED_REFERENCE"])

    def test_forged_exchange_original_rejected(self):
        c=copy.deepcopy(self.chain)
        c["event_types"][2]["first_party_original_observed_in_runner"]=True
        with self.assertRaises(ValueError): normalize(c)

    def test_forged_forecast_effective_rejected(self):
        c=copy.deepcopy(self.chain)
        c["event_types"][1]["is_effective_exchange_delist"]=True
        with self.assertRaises(ValueError): normalize(c)

    def test_wrong_issuer_rejected(self):
        c=copy.deepcopy(self.chain);c["issuer"]="sh.600000"
        with self.assertRaises(ValueError): normalize(c)

    def test_extra_unsupported_event_rejected(self):
        c=copy.deepcopy(self.chain);c["event_types"].append({"type":"AUTO_TRADING"})
        with self.assertRaises(ValueError): normalize(c)

if __name__=="__main__": unittest.main()
