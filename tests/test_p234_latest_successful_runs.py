import unittest
from collector.p234_latest_successful_runs import select,latest

def rows():
    return [
        {"databaseId":10,"conclusion":"success","status":"completed","headBranch":"main","createdAt":"2026-11-06T06:00:00Z"},
        {"databaseId":11,"conclusion":"failure","status":"completed","headBranch":"main","createdAt":"2026-11-06T07:00:00Z"},
        {"databaseId":12,"conclusion":"success","status":"completed","headBranch":"feature/foo","createdAt":"2026-11-06T08:00:00Z"},
        {"databaseId":13,"conclusion":"success","status":"completed","headBranch":"main","createdAt":"2026-11-06T06:30:00Z"},
    ]

class LatestSourceRunTests(unittest.TestCase):
    def test_latest_successful_main_only(self):
        self.assertEqual(select(rows())["run_id"],13)
    def test_bad_or_pending_not_success(self):
        with self.assertRaises(ValueError):select(rows()[1:3])
        with self.assertRaises(ValueError):select([])
        with self.assertRaises(ValueError):select(None)
    def test_distinct_sources_unsynchronized_and_gate(self):
        seq=iter((10,20,30))
        result=latest(lambda workflow:[
            {"databaseId":next(seq),"conclusion":"success",
             "status":"completed","headBranch":"main",
             "createdAt":"2026-11-06T06:00:00Z"}])
        self.assertEqual([result["selection"][x]["run_id"] for x in ("p2","p3","p4")],[10,20,30])
        self.assertFalse(result["cohort_synchronized"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_duplicate_ids_cannot_prove_distinct_sources(self):
        with self.assertRaises(ValueError):latest(lambda _:rows()[:1])
if __name__=="__main__":unittest.main()
