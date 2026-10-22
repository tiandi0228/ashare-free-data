import copy
import json
import unittest
from pathlib import Path
from collector.p3_multi_issuer_research_events import merge_research_ledgers
from collector.p3_two_pdf_event_chain import combine
from collector.p3_typed_event_research_ledger import normalize

class MultiIssuerResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]/"reports"
        a=json.loads((root/"p3_cninfo_600421_early_20261021.json").read_text())
        b=json.loads((root/"p3_cninfo_600421_disclosure_pdf_20261021.json").read_text())
        cls.base=normalize(combine(a,b,"2026-06-22"))

    def test_real_issuer_aggregated_without_trading(self):
        r=merge_research_ledgers([self.base])
        self.assertEqual((r["issuer_count"],r["event_count"]),(1,3))
        self.assertFalse(r["historical_pit_states_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_second_research_issuer_and_chronological_sort(self):
        new=copy.deepcopy(self.base)
        for x in new["rows"]:
            x["issuer"]="sz.000001"
        r=merge_research_ledgers([self.base,new])
        self.assertEqual((r["issuer_count"],r["event_count"]),(2,6))
        self.assertTrue(all(x["confirmed_effective_date"] is None for x in r["rows"]))

    def test_duplicate_source_rejected(self):
        with self.assertRaises(ValueError):merge_research_ledgers([self.base,self.base])

    def test_invalid_issuer_rejected(self):
        a=copy.deepcopy(self.base);a["rows"][0]["issuer"]="sz.300001"
        with self.assertRaises(ValueError):merge_research_ledgers([a])

    def test_forged_state_rejected(self):
        a=copy.deepcopy(self.base);a["rows"][0]["confirmed_effective_date"]="2026-06-01"
        with self.assertRaises(ValueError):merge_research_ledgers([a])

    def test_unverified_reference_cannot_claim_pdf(self):
        a=copy.deepcopy(self.base);a["rows"][2]["source_sha256_receipts"]=["0"*64]
        with self.assertRaises(ValueError):merge_research_ledgers([a])
if __name__=="__main__":unittest.main()
