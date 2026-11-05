"""P1 scale-blocker explainability must not relax any acquisition gate."""
import copy
import unittest
from collector.p1_dual_pilot_blocker_diagnostic import diagnose, TARGET

def row(i,status="completed",conclusion="success"):
    return {"id":i,"event":"schedule","head_branch":"main",
            "path":TARGET,"status":status,"conclusion":conclusion,
            "created_at":"2026-11-04T14:10:00Z"}

def review():
    return {"phase":"P1_DUAL_PILOT_READ_ONLY_SCALE_REVIEW",
            "status":"RECORDED_PILOTS_INTERVENING_SCHEDULE_FAILURE",
            "reviewed_scheduled_run_ids":[8,9,10],
            "schedule_checked_run_ids":[8,9,10,11],
            "schedule_problem_run_ids":[9,11],
            "historical_PIT_verified":False,
            "automatic_shard_increase_authorized":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def hist():
    a=[row(8),row(9,conclusion="failure"),row(10),
       row(11,"in_progress",None)]
    return {"total_count":4,"workflow_runs":a}

class DiagnosticTests(unittest.TestCase):
    def test_independent_problems_are_classified_not_excused(self):
        q=diagnose(review(),hist())
        self.assertEqual(q["problem_count"],2)
        self.assertEqual(q["problem_status_counts"],{"failure":1,"not_completed":1})
        self.assertEqual([x["run_id"] for x in q["problem_runs"]],[11,9])
        self.assertFalse(q["root_cause_verified"])
        self.assertFalse(q["automatic_shard_increase_authorized"])
        self.assertEqual(q["trade_gate"],"BLOCKED")
    def test_wrong_run_history_and_forged_report_block(self):
        changes=(
          lambda r,h:r.update(trade_gate="OPEN"),
          lambda r,h:r.update(automatic_shard_increase_authorized=True),
          lambda r,h:r["schedule_problem_run_ids"].append(8),
          lambda r,h:h["workflow_runs"][0].update(event="workflow_dispatch"),
          lambda r,h:h["workflow_runs"][0].update(head_branch="feature"),
          lambda r,h:h["workflow_runs"][0].update(path="other"),
          lambda r,h:h["workflow_runs"][0].update(id=9),
          lambda r,h:h["workflow_runs"][1].update(conclusion="success"),
        )
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):
                r,h=copy.deepcopy(review()),copy.deepcopy(hist())
                change(r,h);diagnose(r,h)
    def test_missing_history_never_claims_healthy(self):
        h=hist();h["workflow_runs"].pop()
        q=diagnose(review(),h)
        self.assertEqual(q["status"],"HISTORY_INCOMPLETE_NO_DECISION")
        self.assertFalse(q["automatic_shard_increase_authorized"])
    def test_healthy_bounded_report_is_still_not_scaling_authority(self):
        r=review();r["schedule_problem_run_ids"]=[]
        h=hist()
        h["workflow_runs"][1]["conclusion"]="success"
        h["workflow_runs"][3].update(status="completed",conclusion="success")
        q=diagnose(r,h)
        self.assertEqual(q["problem_count"],0)
        self.assertFalse(q["automatic_shard_increase_authorized"])

if __name__=="__main__":unittest.main()
