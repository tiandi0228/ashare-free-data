import unittest
from collector.p3_index_pdf_reconciliation import reconcile
class IndexPdfTests(unittest.TestCase):
    def fixture(self):
        url="https://static.cninfo.com.cn/finalpage/test.pdf"
        index=[{"announcement_id":"123","issuer":"sh.600421","original_url":url,"published_at":"2026-10-20 08:01"}]
        pdf={"trade_gate":"BLOCKED","historical_PIT_eligible":0,"sources":[{"announcement_id":"123","issuer":"sh.600421","url":url,"sha256":"a"*64,"original_bytes_verified":True,"source_id":"sample"}]}
        return index,pdf
    def test_join_is_not_pit_proof(self):
        i,p=self.fixture();r=reconcile(i,p)
        self.assertEqual(r["linked_count"],1)
        self.assertEqual(r["authenticated_first_publication_count"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_wrong_identity_rejected(self):
        i,p=self.fixture();p["sources"][0]["issuer"]="sh.600000"
        with self.assertRaises(ValueError):reconcile(i,p)
    def test_missing_index_record_is_gap(self):
        i,p=self.fixture();r=reconcile([],p)
        self.assertEqual(r["unmatched_pdf_sources"],["sample"])
    def test_duplicate_index_ids_rejected(self):
        i,p=self.fixture()
        with self.assertRaises(ValueError):reconcile(i+i,p)
if __name__=="__main__":unittest.main()
