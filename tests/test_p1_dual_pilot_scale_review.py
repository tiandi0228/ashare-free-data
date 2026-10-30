import base64
import json
import subprocess
import unittest
from unittest.mock import patch

from collector.p1_dual_pilot_scale_review import inspect,load_recent_remote


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
            "trigger_cron_utc":"10 15 * * 1-5" if trigger=="schedule" else None,
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
        self.assertEqual(report["status"],"RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW")
        self.assertEqual(report["reviewed_scheduled_run_ids"],[105,102,100])
        self.assertTrue(report["unrecorded_or_failed_runs_not_excluded"])
        self.assertFalse(report["automatic_shard_increase_authorized"])
        self.assertEqual(report["trade_gate"],"BLOCKED")

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
                         "RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW")

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
                         "RECORDED_PILOTS_READY_FOR_HUMAN_REVIEW")

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
        self.assertIn("github.event.schedule == '10 15 * * 1-5' && '2' || '1'",wf)


if __name__=="__main__":
    unittest.main()
