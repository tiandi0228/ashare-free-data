import unittest
from collector.p1_operational_progress_health import assess, WORKFLOW

def run(outcome="success",id=101):
    return {"id":id,"name":WORKFLOW,"head_branch":"main",
            "event":"schedule","status":"completed","conclusion":outcome}

def bound(before=162,after=163,new=1,id=101):
    return {"run_id":id,"report":{"phase":"P1_READ_ONLY_RUN_PROGRESS",
            "previous_shards":before,"current_shards":after,"new_shard_count":new,
            "trade_gate":"BLOCKED","historical_PIT_verified":False,
            "orders":[],"executable_candidates":[]}}

class P1HealthTests(unittest.TestCase):
    def test_success_alone_never_proves_new_shards(self):
        r=assess(run())
        self.assertTrue(r["workflow_success"])
        self.assertFalse(r["run_bound_progress_verified"])
        self.assertIsNone(r["actual_new_shards"])

    def test_verified_new_shard_is_research_only(self):
        r=assess(run(),bound())
        self.assertEqual(r["progress_status"],"NEW_RESEARCH_SHARDS")
        self.assertEqual((r["prior_shards"],r["current_shards"]),(162,163))
        self.assertEqual(r["actual_new_shards"],1)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["historical_PIT_verified"])

    def test_success_no_progress_not_counted(self):
        r=assess(run(),bound(before=163,after=163,new=0))
        self.assertEqual(r["progress_status"],"SUCCESS_WITHOUT_NEW_SHARDS")
        self.assertEqual(r["actual_new_shards"],0)

    def test_failed_run_never_uses_progress(self):
        r=assess(run("failure"),bound())
        self.assertEqual(r["progress_status"],"WORKFLOW_NOT_SUCCESSFUL")
        self.assertIsNone(r["actual_new_shards"])

    def test_wrong_run_envelope_rejected(self):
        with self.assertRaises(ValueError):
            assess(run(),bound(id=102))

    def test_forged_increment_rejected(self):
        with self.assertRaises(ValueError):
            assess(run(),bound(before=162,after=163,new=3))

    def test_unsafe_or_wrong_workflow_rejected(self):
        p=bound()
        p["report"]["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):
            assess(run(),p)
        with self.assertRaises(ValueError):
            assess(dict(run(),name="unrelated P1 workflow"),bound())

if __name__=="__main__":
    unittest.main()
