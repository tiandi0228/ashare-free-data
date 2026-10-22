"""Real two-CNINFO-document provenance is not official historical coverage."""
import copy
import json
from pathlib import Path
import unittest
from collector.p3_real_receipt_gap import reconcile

ROOT=Path(__file__).resolve().parents[1]
class ReceiptGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt=json.loads((ROOT/"reports/p3_600421_two_pdf_event_chain_20261021.json").read_text())
    def test_real_receipt_has_twenty_eight_unverified_cells(self):
        q=reconcile(self.receipt)
        self.assertEqual(q["required_evidence_cells"],28)
        self.assertEqual(q["verified_evidence_cells"],0)
        self.assertEqual(q["missing_evidence_cells"],28)
        self.assertEqual(q["issuer_documents_observed"],2)
        self.assertEqual(q["trade_gate"],"BLOCKED")
    def test_forged_publication_time_rejected(self):
        x=copy.deepcopy(self.receipt);x["asof_timestamp_authenticated"]=True
        with self.assertRaisesRegex(ValueError,"unrecognized"):
            reconcile(x)
    def test_forged_original_exchange_source_rejected(self):
        x=copy.deepcopy(self.receipt);x["exchange_deletion_effective_original_obtained"]=True
        with self.assertRaisesRegex(ValueError,"unrecognized"):
            reconcile(x)
    def test_wrong_original_digest_rejected(self):
        x=copy.deepcopy(self.receipt);x["source_sha256"][0]="0"*64
        with self.assertRaisesRegex(ValueError,"unrecognized"):
            reconcile(x)

if __name__=="__main__":
    unittest.main()
