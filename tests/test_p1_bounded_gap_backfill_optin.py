"""Opt-in P1 missing-range selection tests. Never call providers or change archives."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.test_p1_quad_pick import PickTests
from collector.p1_quad_pick import choose_gap_window, main


class GapBackfillTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.prior = PickTests().strict_ledger()

    def test_sole_pending_shard_selected_once(self):
        self.assertEqual(choose_gap_window(self.plan,self.prior,"5:6",2),[6])

    def test_reject_window_with_no_missing_shards(self):
        with self.assertRaises(ValueError):
            choose_gap_window(self.plan,self.prior,"0:5",2)

    def test_wrong_epoch_or_corrupt_prior_denied(self):
        bad=copy.deepcopy(self.prior)
        bad["source_sha256"]="b"*64
        with self.assertRaises(ValueError):choose_gap_window(self.plan,bad,"0:6",2)

    def test_bad_window_and_limits_rejected(self):
        for window in ("-1:2","2:1","0:7","0:400","hello","0:2:3", "0: 3"):
            with self.subTest(window=window),self.assertRaises(ValueError):
                choose_gap_window(self.plan,self.prior,window,1)
        for limit in (0,3,True,"2"):
            with self.subTest(limit=limit),self.assertRaises(ValueError):
                choose_gap_window(self.plan,self.prior,"0:6",limit)

    def test_cli_opt_in_is_bounded_without_archive_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            plan=root/"plan.json";prior=root/"prior.json";out=root/"output.txt"
            plan.write_text(json.dumps(self.plan))
            prior.write_text(json.dumps(self.prior))
            args=["p1_quad_pick","--plan",str(plan),"--prior",str(prior),
                  "--output-file",str(out),"--per-run","2","--gap-window","5:6"]
            with patch("sys.argv",args),patch.dict(os.environ,{"GITHUB_RUN_NUMBER":"4"}):
                main()
            flags=dict(line.split("=",1) for line in out.read_text().splitlines())
            self.assertEqual(flags["first"],"0006")
            self.assertEqual(flags["has_second"],"false")
            self.assertEqual(flags["second"],"NONE")

    def test_400_shard_real_shape_avoids_complete_islands(self):
        plan=PickTests().plan()
        plan["shard_count"]=400
        plan["issuer_count"]=400
        plan["shards"]=[
            {"index":i,"name":f"shard_{i:04d}.txt","count":1,"sha256":f"{i+1:064x}"}
            for i in range(400)]
        fakeprior={"source_sha256":"a"*64,"shard_count":400,"trade_gate":"BLOCKED",
                   "phase":"P1_ROSTER_SHARD_LEDGER","historical_PIT_verified":False,
                   "orders":[],"executable_candidates":[],"full_market_bars_certified":False,
                   "completed":[{"index":i,"issuer_count":1,
                                 "manifest_sha256":f"{i+1:064x}",
                                 "receipt_sha256":f"{i+1000:064x}"}
                                for i in list(range(215))+list(range(221,225))+list(range(374,400))],
                   "completed_shards":245,"completed_issuers":245,
                   "pending_shards":list(range(215,221))+list(range(225,374)),
                   "next_shard":215,"failed_in_this_reconciliation":[]}
        self.assertEqual(choose_gap_window(plan,fakeprior,"215:220",2),[215,216])
        self.assertEqual(choose_gap_window(plan,fakeprior,"225:373",2),[225,226])
        self.assertEqual(choose_gap_window(plan,fakeprior,"210:225",2),[215,216])
        with self.assertRaises(ValueError):
            choose_gap_window(plan,fakeprior,"374:399",1)


if __name__=="__main__":
    unittest.main()
