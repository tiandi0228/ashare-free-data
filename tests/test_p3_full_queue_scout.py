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
def p2_source_hint(issuer="sz.000002", shard_id="shard_0002", digest=None,
                   category="VENDOR_SUSPENDED_IN_LAST_21_ROWS"):
    digest=digest or "a"*64
    return {
        "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
        "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
        "source_epoch_sha256":"b"*64,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "actionable_buy_signals":[],"historical_PIT_verified":False,
        "coverage_certified_for_trading":False,
        "gap_repair_queue_is_research_only":True,
        "observed_with_feature_gaps_shards":1,
        "issuer_evidence_gap_count":1,
        "gap_repair_queue":[{
            "shard_id":shard_id,"issuer_gap_count":1,
            "issuer_reasons":[{
                "issuer":issuer,"reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS",
                "original_gap_diagnostic":{
                    "category":category,"original_csv_sha256":digest,
                    "last_21_vendor_rows_suspended":2,
                    "historical_PIT_verified":False,
                    "vendor_calendar_independently_verified":False,
                    "repair_approved":False,
                },
            }],
        }],
    }

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
    def test_p2_original_sha_matched_suspension_priority(self):
        data=q()
        hint=p2_source_hint()
        result=plan(data,p2_coverage=hint)
        self.assertEqual(result["targets"][0]["issuer"],"sz.000002")
        self.assertEqual(result["targets"][0]["target_selection_basis"],
                         "P2_SHA_CHECKED_RECENT_VENDOR_SUSPENSION_NOT_OFFICIAL")
        self.assertEqual(result["p2_original_sha_priority_targets"],1)
        self.assertFalse(result["p2_hint_is_official_evidence"])
        self.assertEqual(len({t["issuer"] for t in result["targets"]}),3)
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_p3_run_number_rotates_sha_checked_suspects_even_when_p1_stalls(self):
        hint=p2_source_hint(issuer="sh.600000",shard_id="shard_0000")
        codes=("sz.000001","sz.000002","sh.600003")
        for index,code in enumerate(codes,1):
            hint["gap_repair_queue"].append({
                "shard_id":f"shard_{index:04d}",
                "issuer_gap_count":1,
                "issuer_reasons":[{
                    "issuer":code,"reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS",
                    "original_gap_diagnostic":{
                        "category":"VENDOR_SUSPENDED_IN_LAST_21_ROWS",
                        "original_csv_sha256":"a"*64,
                        "last_21_vendor_rows_suspended":1,
                        "historical_PIT_verified":False,
                        "vendor_calendar_independently_verified":False,
                        "repair_approved":False,
                    },
                }],
            })
        hint["observed_with_feature_gaps_shards"]=4
        hint["issuer_evidence_gap_count"]=4
        first=plan(q(8),p2_coverage=hint,rotation_index=1)
        second=plan(q(8),p2_coverage=hint,rotation_index=2)
        third=plan(q(8),p2_coverage=hint,rotation_index=3)
        a=[t["issuer"] for t in first["targets"]]
        b=[t["issuer"] for t in second["targets"]]
        self.assertNotEqual(a,b)
        self.assertEqual(len(a),3)
        self.assertEqual(len(b),3)
        self.assertEqual(set(a+b),{"sh.600000","sz.000001","sz.000002","sh.600003"})
        self.assertEqual(first["rotation_basis"],"P3_WORKFLOW_RUN_NUMBER")
        self.assertEqual(first["rotation_index"],1)
        self.assertEqual(second["rotation_index"],2)
        self.assertEqual(third["trade_gate"],"BLOCKED")
        self.assertFalse(third["official_PIT_verified"])
        self.assertEqual(third["orders"],[])

    def test_p3_rotation_index_rejects_invalid_forged_runs(self):
        for value in (True,False,0,-1,1.0,"2",None):
            if value is None:
                self.assertEqual(plan(q())["rotation_basis"],"P1_COMPLETED_SHARDS_LEGACY")
                continue
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    plan(q(),rotation_index=value)
        with self.assertRaises(ValueError):
            plan(q(),rotation_index=1000000001)

    def test_p2_history_shortage_never_becomes_halt_priority(self):
        hint=p2_source_hint(category="FEWER_THAN_21_VENDOR_ROWS_ASOF")
        result=plan(q(),p2_coverage=hint)
        self.assertEqual(result["p2_original_sha_priority_targets"],0)
        self.assertFalse(any(
            t["target_selection_basis"]=="P2_SHA_CHECKED_RECENT_VENDOR_SUSPENSION_NOT_OFFICIAL"
            for t in result["targets"]))

    def test_p2_source_mismatch_and_unsafe_hint_rejected(self):
        import copy
        hint=p2_source_hint()
        for change,value in (
            ("source_epoch_sha256","c"*64),
            ("trade_gate","OPEN"),
            ("issuer_evidence_gap_count",2),
        ):
            bad=copy.deepcopy(hint);bad[change]=value
            with self.subTest(change=change):
                with self.assertRaises(ValueError):plan(q(),p2_coverage=bad)
        for change,value in (
            ("shard_id","shard_0003"),
            ("original_csv_sha256","d"*64),
        ):
            bad=copy.deepcopy(hint)
            if change=="shard_id":bad["gap_repair_queue"][0][change]=value
            else:bad["gap_repair_queue"][0]["issuer_reasons"][0]["original_gap_diagnostic"][change]=value
            with self.subTest(change=change):
                with self.assertRaises(ValueError):plan(q(),p2_coverage=bad)

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
