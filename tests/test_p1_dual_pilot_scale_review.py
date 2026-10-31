import base64
import json
import subprocess
import unittest
from unittest.mock import patch

from collector.p1_dual_pilot_scale_review import inspect,load_recent_remote,verify_actions_conclusions,verify_recent_schedule_health


class P1DualPilotScaleReviewTests(unittest.TestCase):
    EPOCH="a"*64

    def receipt(self,run_id,*,outcome="TWO_VERIFIED_SHARDS_ARCHIVED",
                trigger="schedule",attempt=1):
        selected=[1,2]
        if outcome=="FIRST_ARCHIVED_SECOND_REJECTED":
            accepted=[1];status="SECOND_INVALID_PRESERVE_FIRST"
        elif outcome=="ONLY_ONE_SHARD_PENDING":
            selected=[1];accepted=[1];status="SINGLE_SHARD_REQUESTED"
        elif outcome=="DUAL_PILOT_NOT_YET_PROVEN":
            accepted=[1];status="SECOND_SHARD_VERIFIED"
        else:
            accepted=[1,2];status="SECOND_SHARD_VERIFIED"
        return {
            "phase":"P1_DURABLE_DUAL_SHARD_PILOT_RECEIPT",
            "source_sha256":self.EPOCH,
            "run_id":run_id,"run_attempt":attempt,
            "trigger":trigger,
            "trigger_cron_utc":("10 9 * * 1-5" if run_id%2==0 else "10 15 * * 1-5") if trigger=="schedule" else None,
            "requested_shards":2,
            "selected_shards":selected,
            "new_selected_shards":accepted,
            "new_shards_durably_accepted":len(accepted),
            "dual_pilot_result":outcome,
            "second_policy_status":status,
            "checkpoint_shards_before":44,
            "checkpoint_shards_after":44+len(accepted),
            "archive_csv_replay_enabled":True,
            "archive_gap_issuers":0,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[],
        }

    def test_three_recorded_scheduled_successes_allow_manual_review_only(self):
        rs=[self.receipt(100),self.receipt(105),self.receipt(102)]
        report=inspect(rs,self.EPOCH)
        self.assertEqual(report["status"],"RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION")
        self.assertEqual(report["reviewed_scheduled_run_ids"],[105,102,100])
        self.assertTrue(report["unrecorded_or_failed_runs_not_excluded"])
        self.assertFalse(report["automatic_shard_increase_authorized"])
        self.assertEqual(report["trade_gate"],"BLOCKED")

    def actions_run(self, run_id, *, conclusion="success", status="completed",
                    attempt=1, path=".github/workflows/p1-fresh-vendor-roster.yml",
                    event="schedule", branch="main"):
        return dict(id=run_id, run_attempt=attempt, path=path, event=event,
                    head_branch=branch, status=status, conclusion=conclusion)

    def test_both_daily_pilots_count_for_manual_review_only(self):
        rs=[self.receipt(100),self.receipt(101),self.receipt(102)]
        report=inspect(rs,self.EPOCH)
        self.assertEqual(report["recorded_scheduled_runs"],3)
        self.assertEqual(report["status"],"RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION")
        self.assertFalse(report["automatic_shard_increase_authorized"])
        self.assertEqual(report["trade_gate"],"BLOCKED")

    def test_three_successes_from_only_one_pilot_slot_cannot_scale(self):
        rows=[self.receipt(i) for i in (100,101,102)]
        for row in rows:
            row["trigger_cron_utc"]="10 15 * * 1-5"
        result=inspect(rows,self.EPOCH)
        self.assertEqual(result["recorded_scheduled_runs"],3)
        self.assertEqual(result["status"],
                         "RECENT_SCHEDULED_PILOT_CRON_COVERAGE_INCOMPLETE")
        self.assertFalse(result["both_scheduled_pilot_slots_observed"])
        self.assertEqual(set(result["reviewed_scheduled_crons"]),
                         {"10 15 * * 1-5"})
        self.assertFalse(result["automatic_shard_increase_authorized"])
        self.assertEqual(result["trade_gate"],"BLOCKED")

    def test_both_pilot_slots_required_but_never_auto_authorized(self):
        rows=[self.receipt(i) for i in (100,101,102)]
        result=inspect(rows,self.EPOCH)
        self.assertTrue(result["both_scheduled_pilot_slots_observed"])
        self.assertEqual(set(result["reviewed_scheduled_crons"]),
                         {"10 15 * * 1-5","10 9 * * 1-5"})
        self.assertEqual(result["status"],
                         "RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION")
        self.assertFalse(result["automatic_shard_increase_authorized"])

    def test_unapproved_new_dual_cron_still_rejected(self):
        row=self.receipt(100)
        row["trigger_cron_utc"]="10 3 * * 1-5"
        with self.assertRaisesRegex(ValueError,"untrusted pilot schedule"):
            inspect([row],self.EPOCH)

    def test_two_weekend_crons_are_strictly_one_shard(self):
        from pathlib import Path
        import re
        folder=Path(__file__).resolve().parents[1]
        w=(folder/".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        schedule=w.split("  schedule:",1)[1].split("  workflow_dispatch:",1)[0]
        crons=re.findall(r"^\s*- cron: '([^']+)'",schedule,re.M)
        self.assertEqual(len(crons),12)
        self.assertEqual({c for c in crons if c.endswith("6,0")},
                         {"10 11 * * 6,0","10 15 * * 6,0"})
        formula=next(x for x in w.splitlines() if "P1_REQUESTED_SHARDS:" in x)
        self.assertNotIn("6,0",formula)
        self.assertIn("github.event.schedule == '10 9 * * 1-5'",formula)
        self.assertIn("github.event.schedule == '10 15 * * 1-5'",formula)
        self.assertIn("&& '2' || '1'",formula)
        self.assertIn("assert requested in (1,2)",w)
        self.assertIn("group: p1-fresh-mainboard-roster-serial",w)
        self.assertIn("cancel-in-progress: false",w)
        self.assertIn("python -m collector.p1_archive_audit",w)
        self.assertIn("--replay",w)
        for weekend in ("10 11 * * 6,0","10 15 * * 6,0"):
            receipt=self.receipt(100)
            receipt["trigger_cron_utc"]=weekend
            with self.assertRaisesRegex(ValueError,"untrusted pilot schedule"):
                inspect([receipt],self.EPOCH)

    def test_workflow_has_exactly_two_daily_dual_slots(self):
        from pathlib import Path
        workflow=(Path(__file__).resolve().parents[1]/
                  ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        formula=next(line for line in workflow.splitlines()
                     if "P1_REQUESTED_SHARDS:" in line)
        self.assertIn("github.event.schedule == '10 15 * * 1-5'",formula)
        self.assertIn("github.event.schedule == '10 9 * * 1-5'",formula)
        self.assertIn("&& '2' || '1'",formula)
        self.assertIn("inputs.shards_per_run",formula)
        # No four-shard escalation before repeated verified pilots and review.
        self.assertIn('options: ["1", "2"]',workflow)
        self.assertIn('assert requested in (1,2)',workflow)
        self.assertIn('continue-on-error: true',workflow)
        self.assertIn('python -m collector.p1_archive_audit',workflow)
        self.assertIn('--replay',workflow)

    def test_actions_api_proves_three_completed_scheduled_runs(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=inspect(receipts,self.EPOCH)
        self.assertEqual(report["status"],"RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION")
        def fetch(endpoint,*args,**kwargs):
            run_id=int(endpoint.rsplit("/",1)[1])
            return json.dumps(self.actions_run(run_id))
        with patch("collector.p1_dual_pilot_scale_review.gh",side_effect=fetch) as api:
            approved=verify_actions_conclusions(report,receipts,"o/r")
        self.assertEqual(api.call_count,3)
        self.assertTrue(approved["actions_runs_verified"])
        self.assertEqual(approved["status"],"RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        self.assertFalse(approved["automatic_shard_increase_authorized"])
        self.assertEqual([x["status"] for x in approved["reviewed_actions_conclusions"]],
                         ["CONFIRMED_SUCCESS"]*3)

    def test_actions_failure_pending_bad_workflow_and_retry_do_not_qualify(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=inspect(receipts,self.EPOCH)
        variants=(
            {"conclusion":"failure"},
            {"status":"in_progress","conclusion":None},
            {"path":".github/workflows/other.yml"},
            {"event":"workflow_dispatch"},
            {"branch":"feature"},
            {"attempt":2},
        )
        for variant in variants:
            with self.subTest(variant=variant):
                def fetch(endpoint,*args,**kwargs):
                    run_id=int(endpoint.rsplit("/",1)[1])
                    return json.dumps(self.actions_run(
                        run_id,**(variant if run_id==102 else {})))
                with patch("collector.p1_dual_pilot_scale_review.gh",
                           side_effect=fetch):
                    reviewed=verify_actions_conclusions(report,receipts,"o/r")
                self.assertFalse(reviewed["actions_runs_verified"])
                self.assertEqual(reviewed["status"],
                    "RECORDED_PILOTS_ACTIONS_VERIFICATION_INCOMPLETE")

    def test_current_running_pilot_cannot_self_certify(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=inspect(receipts,self.EPOCH)
        def fetch(endpoint,*args,**kwargs):
            run_id=int(endpoint.rsplit("/",1)[1])
            self.assertNotEqual(run_id,102)
            return json.dumps(self.actions_run(run_id))
        with patch("collector.p1_dual_pilot_scale_review.gh",side_effect=fetch) as api:
            result=verify_actions_conclusions(
                report,receipts,"o/r",current_run_id=102)
        self.assertEqual(api.call_count,2)
        self.assertFalse(result["actions_runs_verified"])
        self.assertIn("CURRENT_RUN_NOT_COMPLETED",
                      [x["status"] for x in result["reviewed_actions_conclusions"]])

    def test_verify_latest_retry_attempt_not_older_duplicate(self):
        receipts=[self.receipt(100),self.receipt(101),
                  self.receipt(102,attempt=2),self.receipt(102,attempt=1)]
        report=inspect(receipts,self.EPOCH)
        def fetch(endpoint,*args,**kwargs):
            run_id=int(endpoint.rsplit("/",1)[1])
            return json.dumps(self.actions_run(run_id,
                             attempt=2 if run_id==102 else 1))
        with patch("collector.p1_dual_pilot_scale_review.gh",side_effect=fetch):
            result=verify_actions_conclusions(report,receipts,"o/r")
        self.assertTrue(result["actions_runs_verified"])

    def test_actions_mismatched_run_id_fail_closed(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=inspect(receipts,self.EPOCH)
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   return_value=json.dumps(self.actions_run(999))):
            with self.assertRaisesRegex(ValueError,"mismatched run ID"):
                verify_actions_conclusions(report,receipts,"o/r")

    def test_cli_review_excludes_running_self_and_verifies_three_previous_runs(self):
        import os
        import tempfile
        from pathlib import Path
        from collector.p1_dual_pilot_scale_review import main
        receipts=[self.receipt(i) for i in (101,102,103,104)]
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/"review.json"
            argv=["p1_dual_pilot_scale_review",
                  "--repo","o/r","--source-sha",self.EPOCH,
                  "--out",str(out)]
            def fetch(endpoint,*args,**kwargs):
                if endpoint.endswith("/runs"):
                    return json.dumps({"total_count":4,"workflow_runs":[
                        self.actions_run(i,**({"status":"in_progress",
                                               "conclusion":None} if i==104 else {}))
                        for i in (104,103,102,101)]})
                run_id=int(endpoint.rsplit("/",1)[1])
                self.assertNotEqual(run_id,104)
                return json.dumps(self.actions_run(run_id))
            with patch("collector.p1_dual_pilot_scale_review.load_recent_remote",
                       return_value=receipts):
                with patch("collector.p1_dual_pilot_scale_review.gh",
                           side_effect=fetch) as api:
                    with patch.dict(os.environ,{"GITHUB_RUN_ID":"104"}):
                        with patch("sys.argv",argv):
                            main()
            report=json.loads(out.read_text())
            self.assertEqual(api.call_count,4)
            self.assertEqual(report["reviewed_scheduled_run_ids"],[103,102,101])
            self.assertEqual(report["status"],"RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW")
            self.assertTrue(report["actions_runs_verified"])
            self.assertFalse(report["automatic_shard_increase_authorized"])

    def test_history_detects_failed_scheduled_run_without_pilot_receipt(self):
        receipts=[self.receipt(i) for i in (100,101,103)]
        report=dict(inspect(receipts,self.EPOCH),
                    status="RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        # Scheduled 102 failed before it could write its permanent receipt.
        history={"total_count":4,"workflow_runs":[
            self.actions_run(103),self.actions_run(102,conclusion="failure"),
            self.actions_run(101),self.actions_run(100)]}
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   return_value=json.dumps(history)) as api:
            decision=verify_recent_schedule_health(report,"o/r")
        self.assertEqual(api.call_count,1)
        self.assertEqual(decision["status"],
                         "RECORDED_PILOTS_INTERVENING_SCHEDULE_FAILURE")
        self.assertEqual(decision["schedule_problem_run_ids"],[102])
        self.assertTrue(decision["schedule_history_complete"])
        self.assertFalse(decision["automatic_shard_increase_authorized"])

    def test_history_confirmed_completed_runs_are_only_human_review(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=dict(inspect(receipts,self.EPOCH),
                    status="RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        history={"total_count":3,"workflow_runs":[
            self.actions_run(102),self.actions_run(101),self.actions_run(100)]}
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   return_value=json.dumps(history)):
            decision=verify_recent_schedule_health(report,"o/r")
        self.assertEqual(decision["status"],
                         "RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW")
        self.assertEqual(decision["schedule_checked_run_ids"],[102,101,100])
        self.assertFalse(decision["automatic_shard_increase_authorized"])

    def test_missing_oldest_run_in_first_page_blocks_review(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=dict(inspect(receipts,self.EPOCH),
                    status="RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        history={"total_count":101,"workflow_runs":[
            self.actions_run(i) for i in range(201,101,-1)]}
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   return_value=json.dumps(history)):
            decision=verify_recent_schedule_health(report,"o/r")
        self.assertEqual(decision["status"],
                         "RECORDED_PILOTS_SCHEDULE_HISTORY_INCOMPLETE")
        self.assertFalse(decision["schedule_history_complete"])

    def test_missing_middle_pilot_run_still_blocks_manual_review(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=dict(inspect(receipts,self.EPOCH),
                    status="RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        # Oldest is present, but a newer scored pilot is absent from
        # this bounded page: claiming complete coverage would be unsafe.
        history={"total_count":3,"workflow_runs":[
            self.actions_run(102),self.actions_run(100),self.actions_run(99)]}
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   return_value=json.dumps(history)):
            result=verify_recent_schedule_health(report,"o/r")
        self.assertEqual(result["status"],
                         "RECORDED_PILOTS_SCHEDULE_HISTORY_INCOMPLETE")
        self.assertFalse(result["schedule_history_complete"])
        self.assertFalse(result["automatic_shard_increase_authorized"])

    def test_underreported_history_total_cannot_certify_complete_coverage(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=dict(inspect(receipts,self.EPOCH),
                    status="RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        history={"total_count":2,"workflow_runs":[
            self.actions_run(102),self.actions_run(101),self.actions_run(100)]}
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   return_value=json.dumps(history)):
            with self.assertRaisesRegex(ValueError,"malformed scheduled workflow history"):
                verify_recent_schedule_health(report,"o/r")

    def test_current_run_in_history_is_not_misclassified_as_failed(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=dict(inspect(receipts,self.EPOCH),
                    status="RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        history={"total_count":4,"workflow_runs":[
            self.actions_run(103,status="in_progress",conclusion=None),
            self.actions_run(102),self.actions_run(101),self.actions_run(100)]}
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   return_value=json.dumps(history)):
            decision=verify_recent_schedule_health(
                report,"o/r",current_run_id=103)
        self.assertEqual(decision["status"],
                         "RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW")
        self.assertNotIn(103,decision["schedule_checked_run_ids"])

    def test_history_missing_or_malformed_run_fails_closed(self):
        receipts=[self.receipt(i) for i in (100,101,102)]
        report=dict(inspect(receipts,self.EPOCH),
                    status="RECORDED_PILOTS_AWAIT_SCHEDULE_HISTORY_CHECK")
        for history in (
            {"total_count":3,"workflow_runs":"invalid"},
            {"total_count":3,"workflow_runs":[self.actions_run(100)]*3},
            {"total_count":3,"workflow_runs":[dict(self.actions_run(100),id=0)]},
        ):
            # Duplicate and invalid IDs cannot certify reliable history.
            with self.subTest(history=history):
                with patch("collector.p1_dual_pilot_scale_review.gh",
                           return_value=json.dumps(history)):
                    with self.assertRaises((ValueError,TypeError)):
                        verify_recent_schedule_health(report,"o/r")

    def test_manual_successes_never_count_as_scheduled(self):
        rs=[self.receipt(100),self.receipt(101,trigger="workflow_dispatch"),
            self.receipt(102,trigger="workflow_dispatch"),self.receipt(103)]
        report=inspect(rs,self.EPOCH)
        self.assertEqual(report["recorded_manual_runs"],2)
        self.assertEqual(report["recorded_scheduled_runs"],2)
        self.assertEqual(report["status"],"INSUFFICIENT_SCHEDULED_PILOT_RECEIPTS")

    def test_latest_recorded_failure_overrides_old_three_successes(self):
        rs=[self.receipt(i) for i in (100,101,102)]
        rs.append(self.receipt(103,outcome="FIRST_ARCHIVED_SECOND_REJECTED"))
        report=inspect(rs,self.EPOCH)
        self.assertEqual(report["status"],"RECENT_RECORDED_PILOT_NOT_ALL_SUCCESSFUL")
        self.assertEqual(report["reviewed_scheduled_run_ids"],[103,102,101])
        self.assertFalse(report["automatic_shard_increase_authorized"])

    def test_latest_run_attempt_is_authoritative(self):
        rs=[self.receipt(i) for i in (101,102,103)]
        rs.append(self.receipt(
            103,outcome="FIRST_ARCHIVED_SECOND_REJECTED",attempt=2))
        report=inspect(rs,self.EPOCH)
        self.assertEqual(report["recorded_total_unique_runs"],3)
        self.assertEqual(report["status"],"RECENT_RECORDED_PILOT_NOT_ALL_SUCCESSFUL")
        self.assertEqual(report["reviewed_scheduled_results"][0],
                         "FIRST_ARCHIVED_SECOND_REJECTED")

    def test_forged_success_invalid_epoch_or_gate_rejected(self):
        for changes in (
            {"source_sha256":"b"*64},{"trade_gate":"OPEN"},
            {"new_shards_durably_accepted":1},
            {"checkpoint_shards_after":49},
            {"trigger_cron_utc":"10 0 * * 1-5"},
            {"historical_PIT_verified":True},
        ):
            with self.subTest(changes=changes):
                receipt=dict(self.receipt(101),**changes)
                with self.assertRaises(ValueError):
                    inspect([receipt],self.EPOCH)

    def test_duplicate_attempt_conflict_rejected(self):
        a=self.receipt(101)
        # Both receipts must be valid individually. A malformed success
        # receipt would be rejected earlier as forged evidence, never reaching
        # the duplicate-attempt conflict check.
        b=dict(a,checkpoint_shards_before=45,checkpoint_shards_after=47)
        self.assertEqual(inspect([a],self.EPOCH)["recorded_total_unique_runs"],1)
        self.assertEqual(inspect([b],self.EPOCH)["recorded_total_unique_runs"],1)
        with self.assertRaisesRegex(ValueError,"conflicting receipts"):
            inspect([a,b],self.EPOCH)

    def test_malformed_success_receipt_is_rejected_before_duplicate_check(self):
        a=self.receipt(101)
        forged=dict(a,second_policy_status="UNTRUSTED")
        with self.assertRaisesRegex(ValueError,"forged two-shard pilot success"):
            inspect([a,forged],self.EPOCH)

    def test_remote_listing_fetches_only_bounded_immutable_receipts(self):
        directory="evidence/pilot_runs/"+self.EPOCH[:16]
        rs=[self.receipt(i) for i in (201,202,203)]
        listing=[{"name":f"run_{i}_attempt_1.json","path":
                  f"{directory}/run_{i}_attempt_1.json","type":"file"}
                 for i in (201,202,203)]
        def fake_gh(endpoint,*args,**kwargs):
            if endpoint==f"repos/o/r/contents/{directory}":
                return json.dumps(listing)
            for record in rs:
                if endpoint.endswith(f"run_{record['run_id']}_attempt_1.json"):
                    return json.dumps({"sha":"blob","type":"file",
                        "path":endpoint.split("/contents/",1)[1],
                        "content":base64.b64encode(json.dumps(record).encode()).decode()})
            raise AssertionError(endpoint)
        with patch("collector.p1_dual_pilot_scale_review.gh",side_effect=fake_gh) as gh:
            fetched=load_recent_remote("o/r",self.EPOCH)
        self.assertEqual([r["run_id"] for r in fetched],[203,202,201])
        self.assertEqual(gh.call_count,4)
        self.assertEqual(inspect(fetched,self.EPOCH)["status"],
                         "RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION")

    def test_remote_blob_run_id_attempt_and_epoch_must_match_filename(self):
        directory="evidence/pilot_runs/"+self.EPOCH[:16]
        name="run_801_attempt_2.json"
        path=f"{directory}/{name}"
        listing=[{"name":name,"path":path,"type":"file"}]
        for record in (
            self.receipt(802,attempt=2),
            self.receipt(801,attempt=1),
            dict(self.receipt(801,attempt=2),source_sha256="b"*64),
        ):
            with self.subTest(actual_id=record["run_id"],
                              actual_attempt=record["run_attempt"],
                              source=record["source_sha256"][:4]):
                data=base64.b64encode(json.dumps(record).encode()).decode()
                with patch("collector.p1_dual_pilot_scale_review.gh",
                           side_effect=[json.dumps(listing),
                                        json.dumps({"sha":"blob","content":data,
                                                    "path":path,"type":"file"})]):
                    with self.assertRaisesRegex(ValueError,"path and source identity mismatch"):
                        load_recent_remote("o/r",self.EPOCH)
        good=self.receipt(801,attempt=2)
        data=base64.b64encode(json.dumps(good).encode()).decode()
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   side_effect=[json.dumps(listing),
                                json.dumps({"sha":"blob","content":data,
                                            "path":path,"type":"file"})]):
            self.assertEqual(load_recent_remote("o/r",self.EPOCH),[good])

    def test_remote_pilot_blob_cannot_claim_different_contents_path(self):
        directory="evidence/pilot_runs/"+self.EPOCH[:16]
        name="run_801_attempt_1.json"
        path=f"{directory}/{name}"
        listing=[{"name":name,"path":path,"type":"file"}]
        good=self.receipt(801)
        data=base64.b64encode(json.dumps(good).encode()).decode()
        with patch("collector.p1_dual_pilot_scale_review.gh",
                   side_effect=[json.dumps(listing),
                                json.dumps({"sha":"blob","content":data,
                                            "path":directory+"/run_802_attempt_1.json",
                                            "type":"file"})]):
            with self.assertRaisesRegex(ValueError,"mismatched permanent pilot blob"):
                load_recent_remote("o/r",self.EPOCH)

    def test_missing_directory_is_no_evidence_and_auth_failure_is_fatal(self):
        absent=subprocess.CalledProcessError(1,["gh","api"],
                          stderr="gh: Not Found (HTTP 404)")
        forbidden=subprocess.CalledProcessError(1,["gh","api"],
                          stderr="gh: Forbidden (HTTP 403)")
        with patch("collector.p1_dual_pilot_scale_review.gh",side_effect=absent):
            self.assertEqual(load_recent_remote("o/r",self.EPOCH),[])
        with patch("collector.p1_dual_pilot_scale_review.gh",side_effect=forbidden):
            with self.assertRaises(subprocess.CalledProcessError):
                load_recent_remote("o/r",self.EPOCH)

    def test_malformed_remote_marker_and_unbounded_listing_rejected(self):
        directory="evidence/pilot_runs/"+self.EPOCH[:16]
        malformed=[{"name":"run_1_attempt_1.json",
                    "path":directory+"/incorrect.json","type":"file"}]
        for listing in (malformed,[{"name":"readme"}]*1000):
            with self.subTest(length=len(listing)):
                with patch("collector.p1_dual_pilot_scale_review.gh",
                           return_value=json.dumps(listing)):
                    with self.assertRaises(ValueError):
                        load_recent_remote("o/r",self.EPOCH)

    def test_more_than_one_hundred_receipts_still_bounded_to_twelve_reads(self):
        directory="evidence/pilot_runs/"+self.EPOCH[:16]
        listing=[
            {"name":f"run_{i}_attempt_1.json",
             "path":f"{directory}/run_{i}_attempt_1.json",
             "type":"file"} for i in range(1,152)
        ]
        def fake_gh(endpoint,*args,**kwargs):
            if endpoint.endswith(directory):
                return json.dumps(listing)
            import re
            match=re.search(r"run_(\d+)_attempt_1\.json$",endpoint)
            if match is None:
                raise AssertionError(endpoint)
            receipt=self.receipt(int(match.group(1)))
            return json.dumps({"sha":"blob","type":"file",
                "path":endpoint.split("/contents/",1)[1],
                "content":base64.b64encode(json.dumps(receipt).encode()).decode()})
        with patch("collector.p1_dual_pilot_scale_review.gh",side_effect=fake_gh) as gh:
            rows=load_recent_remote("o/r",self.EPOCH)
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[0]["run_id"],151)
        self.assertEqual(rows[-1]["run_id"],140)
        self.assertEqual(gh.call_count,13)
        self.assertEqual(inspect(rows,self.EPOCH)["status"],
                         "RECORDED_PILOTS_AWAIT_ACTIONS_VERIFICATION")

    def test_all_p1_unit_tests_run_offline_without_triggering_vendor(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        live=(root/".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        offline=(root/".github/workflows/p1-readiness-contract-ci.yml").read_text()
        live_push=live.split("  schedule:",1)[0]
        self.assertNotIn("      - 'tests/",live_push)
        live_cmd=next(line for line in live.splitlines()
                      if "python -m unittest tests.test_p1_fresh_vendor_roster" in line)
        modules=live_cmd.split("python -m unittest ",1)[1].split(" -v",1)[0].split()
        self.assertGreaterEqual(len(modules),22)
        self.assertEqual(len(modules),len(set(modules)))
        for module in modules:
            self.assertTrue(module.startswith("tests.test_"))
            self.assertIn("            "+module,offline)
            file_path=module.replace(".","/")+".py"
            self.assertEqual(
                offline.count("      - '"+file_path+"'"),2,
                "missing push and pull_request offline paths: "+file_path)
        self.assertIn("  schedule:",live)
        self.assertIn("  workflow_dispatch:",live)
        self.assertIn("      - 'collector/p1_quad_verify.py'",live_push)
        self.assertIn("      - '.github/workflows/p1-fresh-vendor-roster.yml'",live_push)
        self.assertIn("            tests.test_p1_research_readiness \\\n            -v",offline)
        self.assertIn("assert result['trade_gate'] == 'BLOCKED'",offline)

    def test_read_only_scale_review_edits_use_offline_ci_not_vendor_capture(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        live=(root/".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        offline=(root/".github/workflows/p1-readiness-contract-ci.yml").read_text()
        push=live.split("  schedule:",1)[0]
        # Editing a read-only pilot report or its tests must never call the
        # free vendor, persist a new shard or cascade into P3/P4 research jobs.
        for path in ("collector/p1_dual_pilot_scale_review.py",
                     "tests/test_p1_dual_pilot_scale_review.py"):
            needle="      - '"+path+"'"
            self.assertNotIn(needle,push)
            self.assertIn(needle,offline)
        self.assertIn("  pull_request:",offline)
        self.assertIn("  schedule:",live)
        self.assertIn("  workflow_dispatch:",live)
        # Genuine data-source and receipt logic still reach live P1 when edited.
        self.assertIn("      - 'collector/p1_fresh_vendor_roster.py'",push)
        self.assertIn("      - 'collector/p1_dual_pilot_receipt.py'",push)
        self.assertIn("  workflow_run:",(root/".github/workflows/p4-real-ma20-forward-observation.yml").read_text())

    def test_actions_review_does_not_change_scheduler(self):
        from pathlib import Path
        wf=(Path(__file__).resolve().parents[1]/
            ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        a=wf.index("      - name: Persist two-shard pilot evidence")
        b=wf.index("      - name: Assess recorded pilot evidence without scaling")
        c=wf.index("      - name: Independently classify P1 coverage",b)
        self.assertLess(a,b)
        self.assertLess(b,c)
        step=wf[b:c]
        self.assertIn("if: env.P1_REQUESTED_SHARDS == '2'",step)
        self.assertIn("p1_dual_pilot_scale_review",step)
        self.assertIn("evidence/dual_pilot_scale_review.json",step)
        self.assertIn("tests.test_p1_dual_pilot_scale_review",wf)
        self.assertIn("github.event.schedule == '10 15 * * 1-5'",wf)
        self.assertIn("github.event.schedule == '10 9 * * 1-5'",wf)
        self.assertIn("&& '2' || '1'",wf)


if __name__=="__main__":
    unittest.main()
