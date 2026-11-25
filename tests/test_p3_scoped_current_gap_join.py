import unittest
from collector.p3_scoped_current_gap_join import join,EXPECTED,ARCHIVE

def fixture():
    safe=dict(trade_gate="BLOCKED",orders=[],executable_candidates=[],historical_PIT_verified=False)
    h="a"*64
    k="b"*64
    epoch="c"*64
    issuer="sh.600825"
    reports=[dict(safe,issuer=i,archive_commit=ARCHIVE,entire_issuer_gap_closed=False,vendor_csv_sha256=h,notices=[dict(sha256=k,official_first_release=None)]) for i in EXPECTED]
    row=dict(issuer=issuer,source_epoch_sha256=epoch,vendor_csv_sha256=h,buy_eligible=False,feature_gap_resolved=False,official_first_publication_verified=False,complete_official_state_interval_certified=False,original_halt_resume_text_documents=[dict(issuer=issuer,original_pdf_sha256=k)],original_resume_research_text_pairs=[])
    return dict(safe,phase="P3_GAP_ISSUER_ORIGINAL_PDF_PROVENANCE_REVIEW_INDEX",authenticated_first_publication_count=0,certified_exchange_intervals=0,feature_gaps_resolved=0,source_epoch_sha256=epoch,gap_issuer_count=1,issuers=[row],p2_source_run_id=1,p3_source_run_id=2),reports

class TestJoin(unittest.TestCase):
    def test_exact(self):
        a,b=fixture()
        r=join(a,b)
        self.assertEqual(r["issuer_notice_matches"],1)
        self.assertEqual(r["feature_gaps_resolved"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_csv_mismatch(self):
        a,b=fixture()
        a["issuers"][0]["vendor_csv_sha256"]="d"*64
        self.assertEqual(join(a,b)["issuer_notice_matches"],0)
    def test_wrong_pdf(self):
        a,b=fixture()
        a["issuers"][0]["original_halt_resume_text_documents"][0]["original_pdf_sha256"]="e"*64
        self.assertEqual(join(a,b)["issuer_notice_matches"],0)
    def test_forged_clock(self):
        a,b=fixture()
        b[0]["notices"][0]["official_first_release"]="2026-10-01"
        with self.assertRaises(ValueError): join(a,b)
    def test_missing_replay(self):
        a,b=fixture()
        with self.assertRaises(ValueError): join(a,b[:-1])
    def test_cross_issuer(self):
        a,b=fixture()
        a["issuers"][0]["original_halt_resume_text_documents"][0]["issuer"]="sz.002860"
        with self.assertRaises(ValueError): join(a,b)
