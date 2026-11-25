import unittest
from collector.p3_scoped_current_gap_join import join,EXPECTED,ARCHIVE,EXTRA,normalize

def fixture():
    safe=dict(trade_gate="BLOCKED",orders=[],executable_candidates=[],historical_PIT_verified=False)
    h="a"*64
    k="b"*64
    epoch="c"*64
    issuer="sh.600825"
    reports=[dict(safe,issuer=i,archive_commit=ARCHIVE,entire_issuer_gap_closed=False,vendor_csv_sha256=h,notices=[dict(sha256=k,official_first_release=None)]) for i in EXPECTED-EXTRA.keys()]
    for i,archive in EXTRA.items():
        common=dict(safe,issuer=i,phase="P3_BOUNDED_OFFICIAL_TEXT_VENDOR_STATUS_MATCH",archive_commit=archive,vendor_csv_sha256=h,first_publication_time_verified=False,full_halt_interval_certified=False,p2_feature_gaps_resolved=0)
        if i=="sz.000582": common["official_originals"]={"halt":{"sha256":k},"resume":{"sha256":"f"*64}}
        else: common.update(official_pdf_digests_match_pinned_originals=True,notice_originals=[dict(announcement_number="2026-064",observed_pdf_sha256=k),dict(announcement_number="2026-066",observed_pdf_sha256="f"*64)])
        reports.append(common)
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
        next(r for r in b if r["issuer"] not in EXTRA)["notices"][0]["official_first_release"]="2026-10-01"
        with self.assertRaises(ValueError): join(a,b)
    def test_missing_replay(self):
        a,b=fixture()
        with self.assertRaises(ValueError): join(a,b[:-1])
    def test_cross_issuer(self):
        a,b=fixture()
        a["issuers"][0]["original_halt_resume_text_documents"][0]["issuer"]="sz.002860"
        with self.assertRaises(ValueError): join(a,b)

    def test_extra_clock_rejected(self):
        a,b=fixture()
        next(r for r in b if r["issuer"]=="sz.000582")["first_publication_time_verified"]=True
        with self.assertRaises(ValueError): join(a,b)
    def test_extra_archive_rejected(self):
        a,b=fixture()
        next(r for r in b if r["issuer"]=="sz.000668")["archive_commit"]=ARCHIVE
        with self.assertRaises(ValueError): join(a,b)

    def test_partial_calendar_separate_from_original_pdf_matches(self):
        a,b=fixture()
        r=dict(a["issuers"][0],issuer="sh.603183",original_halt_resume_text_documents=[])
        a["issuers"].append(r)
        a["gap_issuer_count"]=2
        partial=dict(issuer="sh.603183",archive_commit=ARCHIVE,status="VENDOR_ROWS_MATCH_RESEARCH_INTERVAL_ORIGINAL_NOTICES_PENDING",outcome_counts={"MATCH":3,"SCHEDULED_CLOSURE":7},issuer_halt_notice_authenticated=False,announcement_available_before_open_verified=False,p2_gap_closed=False,vendor_csv_sha256="a"*64,notice_candidates=[dict(announcement=n,original_pdf_verified=False,original_pdf_sha256=None) for n in ("2026-021","2026-022")],trade_gate="BLOCKED",orders=[],executable_candidates=[],historical_PIT_verified=False)
        out=join(a,b,partial)
        self.assertEqual(out["partial_calendar_csv_matches"],1)
        self.assertEqual(out["issuer_csv_matches"],1)
        self.assertEqual(out["issuer_notice_matches"],1)
        self.assertEqual(out["partial_calendar_replay"]["matched_vendor_days"],3)
        self.assertFalse(out["partial_calendar_replay"]["original_pdf_verified"])
        partial["vendor_csv_sha256"]="d"*64
        self.assertEqual(join(a,b,partial)["partial_calendar_csv_matches"],0)
        partial["notice_candidates"][0]["original_pdf_verified"]=True
        with self.assertRaises(ValueError): join(a,b,partial)

    def test_dynamic_source_run_and_epoch(self):
        a,b=fixture()
        result=join(a,b,crosswalk_run=123,expected_epoch="c"*64)
        self.assertEqual(result["source_crosswalk_run"],123)
        with self.assertRaisesRegex(ValueError,"stale"):
            join(a,b,crosswalk_run=123,expected_epoch="d"*64)
        with self.assertRaises(ValueError):
            join(a,b,crosswalk_run=0)
