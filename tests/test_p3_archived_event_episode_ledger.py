import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p3_archived_event_episode_ledger import build

class CrossRunEventTests(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root=Path(self.work.name)
        (self.root/"runs").mkdir()
        self.pdfs={}
    def notice(self,issuer,notice_id,payload=b"a"):
        content=b"%PDF-1.4\n"+payload*3100
        digest=hashlib.sha256(content).hexdigest()
        rel=f"pdf/{issuer.replace('.','_')}/{notice_id}/{digest}.pdf"
        p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
        self.pdfs[(issuer,notice_id)]=(digest,rel,len(content))
        return {"issuer":issuer,"announcement_id":notice_id,
                "original_retrieved":True,"archive_path":rel,"pdf_sha256":digest,
                "captured_at_utc":"2026-11-04T08:40:00+00:00",
                "bytes":len(content)}
    def claim(self,receipt,day,direction,decision=None,excerpt=None):
        cday=f"{day[:4]}年{int(day[5:7])}月{int(day[8:10])}日"
        return {"issuer":receipt["issuer"],"announcement_id":receipt["announcement_id"],
            "source_date_text":cday,"decision_day":decision or day,
            "local_textual_direction_candidate":direction,
            "source_clause_excerpt":excerpt or f"本公司股票自{cday}起{'停牌' if direction=='HALT_START' else '复牌'}",
            "original_pdf_sha256":receipt["pdf_sha256"],
            "effective_date_authenticated":False,
            "first_publication_authenticated":False,
            "decision_time_available_certified":False}
    def save_run(self,n,receipts,claims):
        item={"phase":"P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE",
              "run_id":n,"trade_gate":"BLOCKED","orders":[],
              "historical_PIT_verified":False,
              "certified_first_publication_count":0,
              "certified_event_effective_day_count":0,
              "certified_historical_decision_state_count":0,
              "original_pdf_count":len(receipts),
              "source_roster_sha256":"b"*64,
              "source_pdf_receipts":receipts,
              "research_date_action_links":claims}
        (self.root/"runs"/f"{n}.json").write_text(json.dumps(item))
        return item
    def test_unpaired_halt_not_real_continuing_halt(self):
        receipt=self.notice("sh.600319","100001")
        self.save_run(100,[receipt],[self.claim(receipt,"2025-11-04","HALT_START"),
                                self.claim(receipt,"2025-11-04","HALT_START","2025-11-17")])
        report=build(self.root)
        self.assertEqual(report["raw_text_assertion_references"],2)
        self.assertEqual(report["deduplicated_text_event_claims"],1)
        first=report["research_text_event_claims"][0]
        self.assertEqual(first["original_first_archived_research_run_id"],100)
        self.assertEqual(first["original_first_archived_research_capture_at_utc"],
                         "2026-11-04T08:40:00+00:00")
        self.assertTrue(first["original_research_capture_after_claimed_event_text_day"])
        self.assertTrue(first["research_capture_not_official_first_publication"])
        self.assertEqual(report["official_first_publication_authenticated_from_capture"],0)
        self.assertEqual(report["unpaired_halt_starts_needing_resumption_search"],1)
        self.assertEqual(report["official_resumption_followups"][0]["warning"],
                         "NO_RESUME_IN_BOUNDED_ARCHIVE_IS_NOT_PROOF_OF_CONTINUING_HALT")
        self.assertFalse(report["complete_issuer_halt_intervals_certified"])
    def test_cross_run_same_notice_collapses_and_resume_never_certified(self):
        a=self.notice("sh.600319","100001")
        b=self.notice("sh.600319","100002",b"b")
        self.save_run(100,[a],[self.claim(a,"2025-11-04","HALT_START")])
        self.save_run(101,[a,b],[self.claim(a,"2025-11-04","HALT_START"),
                             self.claim(b,"2025-11-12","RESUME_START")])
        report=build(self.root)
        self.assertEqual(report["runs_replayed"],2)
        self.assertEqual(report["unique_original_pdfs_sha_replayed"],2)
        self.assertEqual(report["raw_text_assertion_references"],3)
        self.assertEqual(report["deduplicated_text_event_claims"],2)
        self.assertEqual(report["paired_halt_resume_text_claims_unverified"],1)
        self.assertEqual(report["unpaired_halt_starts_needing_resumption_search"],0)
        self.assertFalse(report["paired_event_texts"][0]["issuer_interval_certified"])
        self.assertEqual(report["official_PIT_cells_certified"],0)
    def test_capture_is_minimum_observed_archived_timestamp_not_publication(self):
        original=self.notice("sh.600319","100001")
        old=copy.deepcopy(original)
        newer=copy.deepcopy(original)
        old["captured_at_utc"]="2026-11-04T08:40:00+00:00"
        newer["captured_at_utc"]="2026-11-04T09:40:00+00:00"
        self.save_run(100,[newer],[self.claim(newer,"2025-11-04","HALT_START")])
        self.save_run(101,[old],[self.claim(old,"2025-11-04","HALT_START")])
        r=build(self.root)
        claim=r["research_text_event_claims"][0]
        self.assertEqual(claim["original_first_archived_research_run_id"],101)
        self.assertEqual(claim["original_first_archived_research_capture_at_utc"],
                         "2026-11-04T08:40:00+00:00")
        self.assertEqual(claim["original_sha_verified_archive_path"],
                         original["archive_path"])
        self.assertEqual(r["claims_with_sha_pinned_first_research_capture"],1)
        self.assertEqual(r["claims_first_archive_capture_after_event_text_day"],1)
        self.assertEqual(r["official_first_publication_authenticated_from_capture"],0)
        self.assertFalse(r["historical_PIT_verified"])

    def test_naive_capture_and_wrong_archive_path_rejected(self):
        for mutate in (
            lambda d:d.update(captured_at_utc="2026-11-04T08:40:00"),
            lambda d:d.update(captured_at_utc="invalid"),
            lambda d:d.pop("captured_at_utc"),
            lambda d:d.update(archive_path="pdf/forged.pdf"),
        ):
            with self.subTest(mutate=mutate):
                with tempfile.TemporaryDirectory() as work:
                    root=Path(work)
                    (root/"runs").mkdir()
                    r=self.notice("sh.600319","100001")
                    mutated=copy.deepcopy(r)
                    mutate(mutated)
                    item={
                        "phase":"P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE",
                        "run_id":7,"trade_gate":"BLOCKED","orders":[],
                        "historical_PIT_verified":False,
                        "certified_first_publication_count":0,
                        "certified_event_effective_day_count":0,
                        "certified_historical_decision_state_count":0,
                        "original_pdf_count":1,
                        "source_roster_sha256":"b"*64,
                        "source_pdf_receipts":[mutated],
                        "research_date_action_links":[self.claim(r,"2025-11-04","HALT_START")],
                    }
                    # Source original byte in a separate test folder
                    raw=(self.root/r["archive_path"]).read_bytes()
                    file=root/r["archive_path"]
                    file.parent.mkdir(parents=True,exist_ok=True)
                    file.write_bytes(raw)
                    (root/"runs"/"7.json").write_text(json.dumps(item))
                    with self.assertRaises((ValueError,TypeError)):
                        build(root)

    def test_approval_only_is_not_effective_st_removal(self):
        r=self.notice("sh.600303","100005")
        claim=self.claim(r,"2025-04-17","ST_REMOVED",
                         excerpt="上海证券交易所于2025年4月17日同意公司撤销其他风险警示")
        self.save_run(7,[r],[claim])
        report=build(self.root)
        self.assertEqual(report["approval_consent_is_not_effective_date_count"],1)
        self.assertFalse(report["historical_PIT_verified"])
    def test_resume_without_archived_start_is_not_proof(self):
        r=self.notice("sh.600302","100006")
        self.save_run(7,[r],[self.claim(r,"2026-04-30","RESUME_START")])
        report=build(self.root)
        self.assertEqual(report["unpaired_resume_claims"],1)
        self.assertEqual(report["paired_halt_resume_text_claims_unverified"],0)
    def test_repeat_halt_without_resume_is_flagged(self):
        a=self.notice("sh.600319","100001")
        b=self.notice("sh.600319","100002",b"b")
        self.save_run(7,[a,b],[self.claim(a,"2025-11-04","HALT_START"),
                          self.claim(b,"2025-11-07","HALT_START")])
        report=build(self.root)
        self.assertEqual(report["overlapping_halt_claims_without_resume"],1)
        self.assertEqual(report["unpaired_halt_starts_needing_resumption_search"],1)
    def test_hash_mutation_is_detected_before_any_episode(self):
        r=self.notice("sh.600319","100001")
        self.save_run(7,[r],[self.claim(r,"2025-11-04","HALT_START")])
        (self.root/r["archive_path"]).write_bytes(b"%PDF-mutated")
        with self.assertRaises(ValueError):build(self.root)
    def test_reused_notice_id_with_different_valid_sha_fails(self):
        r=self.notice("sh.600319","100001")
        self.save_run(7,[r],[self.claim(r,"2025-11-04","HALT_START")])
        new=self.notice("sh.600319","100001",b"b")
        self.save_run(8,[new],[self.claim(new,"2025-11-04","HALT_START")])
        with self.assertRaises(ValueError):build(self.root)
    def test_historical_certification_claim_blocked(self):
        r=self.notice("sh.600319","100001")
        item=self.save_run(7,[r],[self.claim(r,"2025-11-04","HALT_START")])
        item["research_date_action_links"][0]["decision_time_available_certified"]=True
        (self.root/"runs/7.json").write_text(json.dumps(item))
        with self.assertRaises(ValueError):build(self.root)
    def test_malformed_date_not_used(self):
        r=self.notice("sh.600319","100001")
        item=self.claim(r,"2025-11-04","HALT_START")
        item["source_date_text"]="2025年2月30日"
        item["source_clause_excerpt"]="自2025年2月30日起停牌"
        self.save_run(7,[r],[item])
        with self.assertRaises(ValueError):build(self.root)
    def test_no_source_runs_not_silent_empty_pass(self):
        with self.assertRaises(ValueError):build(self.root)

if __name__=="__main__":unittest.main()
