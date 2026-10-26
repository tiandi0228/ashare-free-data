import unittest
from collector.p3_full_queue_scout import plan
from collector.p3_full_queue_source_join import reconcile
def q(shards=8):
    tasks=[]
    for idx,code in enumerate(("sh.600000","sz.000001","sz.000002","sh.600003")):
        for kind in ("listing","st","halt","delisting"):
            tasks.append({"issuer":code,"decision_day":"2026-10-20","status_kind":kind,
                          "source_shard":idx,"vendor_csv_sha256":"a"*64,
                          "status":"OFFICIAL_PIT_EVIDENCE_REQUIRED",
                          "historical_asof_verified":False,
                          "official_publisher_authenticated":False,
                          "whole_day_state_coverage_authenticated":False,
                          "official_original_sha256":None,
                          "official_first_publication_utc":None})
    return {"phase":"P3_ALL_COMPLETED_P1_OFFICIAL_PIT_WORKLIST",
            "trade_gate":"BLOCKED","orders":[],
            "historical_PIT_verified":False,
            "independently_verified_official_PIT_cells":0,
            "full_historical_status_coverage_authenticated":False,
            "latest_quote_freshness_authenticated":False,
            "completed_issuers_replayed":4,
            "completed_shards_replayed":shards,
            "required_official_evidence_cells":len(tasks),
            "official_evidence_tasks":tasks,
            "roster_source_sha256":"b"*64,
            "frozen_vendor_query_end":"2026-10-20"}
def fixture():
    queue=q();scout=plan(queue)
    index={"phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY","trade_gate":"BLOCKED",
           "orders":[],"historical_PIT_verified":False,
           "attempted":3,"results":[{"issuer":x["issuer"]} for x in scout["targets"]]}
    originals={"phase":"P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE",
               "trade_gate":"BLOCKED","orders":[],"historical_PIT_verified":False,
               "retrieved":1,"sources":[{"issuer":scout["targets"][0]["issuer"],
                   "announcement_id":"123","sha256":"c"*64,
                   "original_bytes_verified":True,
                   "historical_first_publication_authenticated":False}]}
    replay={"phase":"P3_REAL_P1_ORIGINAL_INDEPENDENT_REPLAY",
            "trade_gate":"BLOCKED","orders":[],"independently_sha_verified":1,
            "historical_first_publication_authenticated":False}
    triage={"phase":"P3_REAL_P1_DATE_CONTEXT_TRIAGE","trade_gate":"BLOCKED",
            "orders":[],"historical_PIT_verified":False,
            "candidate_contexts":[{"issuer":scout["targets"][0]["issuer"],
               "announcement_id":"123","original_sha256":"c"*64,
               "candidate_event_cues":["TRADING_HALT_CUE"],
               "date_text":"2026年10月20日",
               "historical_effective_date_verified":False,
               "historical_publication_time_verified":False}]}
    return [queue,scout,index,originals,replay,triage]
class Tests(unittest.TestCase):
    def test_rotate_only_three_from_all_completed(self):
        s=plan(q())
        self.assertEqual(len(s["targets"]),3)
        self.assertEqual(s["full_source_issuers"],4)
        self.assertEqual(s["unmatched_cells"],12)
    def test_rotation_differs_after_new_shards(self):
        self.assertNotEqual([x["issuer"] for x in plan(q(8))["targets"]],
                            [x["issuer"] for x in plan(q(12))["targets"]])
    def test_prioritize_vendor_nontrading_not_official(self):
        r=q()
        r["vendor_suspended_context_included"]=True
        for row in r["official_evidence_tasks"]:
            row["vendor_tradestatus_observed"]="0" if row["issuer"]=="sz.000002" else "1"
        result=plan(r)
        self.assertEqual(result["targets"][0]["issuer"],"sz.000002")
        self.assertEqual(result["targets"][0]["vendor_suspended_research_days"],["2026-10-20"])
        self.assertEqual(result["targets"][0]["vendor_halt_transition_research_days"],[])
        self.assertEqual(result["vendor_nontrading_research_targets"],1)
        self.assertFalse(result["official_PIT_verified"])
    def test_vendor_transition_requires_nontrading(self):
        r=q()
        r["vendor_suspended_context_included"]=True
        for row in r["official_evidence_tasks"]:row["vendor_tradestatus_observed"]="1"
        r["official_evidence_tasks"][0]["vendor_possible_halt_transition_observed"]=True
        with self.assertRaises(ValueError):plan(r)
    def test_inconsistent_vendor_status_fails_closed(self):
        r=q()
        r["vendor_suspended_context_included"]=True
        for row in r["official_evidence_tasks"]:row["vendor_tradestatus_observed"]="1"
        r["official_evidence_tasks"][0]["vendor_tradestatus_observed"]="0"
        with self.assertRaises(ValueError):plan(r)
    def test_reject_fake_pit_and_duplicate(self):
        data=q();data["official_evidence_tasks"][0]["historical_asof_verified"]=True
        with self.assertRaises(ValueError):plan(data)
    def test_replay_sha_and_scope_join_without_pit(self):
        x=reconcile(*fixture())
        self.assertEqual(x["research_issuer_day_date_cue_links"],1)
        self.assertEqual(x["official_PIT_cells_certified"],0)
        self.assertEqual(x["trade_gate"],"BLOCKED")
    def test_far_away_date_context_not_joined(self):
        args=fixture()
        args[5]["candidate_contexts"][0]["date_text"]="2026年2月18日"
        report=reconcile(*args)
        self.assertEqual(report["research_issuer_day_date_cue_links"],0)
        self.assertEqual(report["out_of_window_candidate_pairs_excluded"],1)
        self.assertEqual(report["official_PIT_cells_certified"],0)
    def test_duplicate_context_only_one_research_link(self):
        args=fixture()
        args[5]["candidate_contexts"].append(dict(args[5]["candidate_contexts"][0]))
        report=reconcile(*args)
        self.assertEqual(report["research_issuer_day_date_cue_links"],1)
        self.assertEqual(report["duplicated_candidate_pairs_excluded"],1)
    def test_invalid_date_text_rejected(self):
        args=fixture()
        args[5]["candidate_contexts"][0]["date_text"]="2026年2月30日"
        with self.assertRaises(ValueError):reconcile(*args)
    def test_vendor_nontrading_research_link_never_pit_certified(self):
        args=fixture()
        issuer=args[1]["targets"][0]["issuer"]
        for cell in args[0]["official_evidence_tasks"]:
            if cell["issuer"]==issuer and cell["status_kind"]=="halt":
                cell["vendor_tradestatus_observed"]="0"
        report=reconcile(*args)
        self.assertEqual(report["vendor_nontrading_date_context_links_research_only"],1)
        self.assertFalse(report["historical_PIT_verified"])
    def test_reject_pdf_sha_mismatch(self):

        args=fixture()
        args[5]["candidate_contexts"][0]["original_sha256"]="d"*64
        with self.assertRaises(ValueError):reconcile(*args)
    def test_missing_index_issuer_is_not_clearance(self):
        args=fixture()
        args[2]["results"]=args[2]["results"][:2]
        with self.assertRaises(ValueError):reconcile(*args)
if __name__=="__main__":unittest.main()
