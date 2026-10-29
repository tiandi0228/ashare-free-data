import unittest
from collector.p1_quad_pick import choose,rotating_start
class PickTests(unittest.TestCase):
    def plan(self):
        return {"phase":"P1_FRESH_VENDOR_SHARD_PLAN","trade_gate":"BLOCKED",
                "source_sha256":"a"*64,"shard_count":7,
                "shards":[{"index":i} for i in range(7)]}
    def test_four_missing(self):
        self.assertEqual(choose(self.plan(),start_index=3),[3,4,5,6])
    def test_wrap_and_skip_completed(self):
        prior={"source_sha256":"a"*64,"shard_count":7,"trade_gate":"BLOCKED",
               "completed":[{"index":i} for i in [0,1,2,3,4]]}
        self.assertEqual(choose(self.plan(),prior,start_index=2),[5,6])
    def test_run_rotation_avoids_permanent_failed_shard_starvation(self):
        prior={"source_sha256":"a"*64,"shard_count":7,"trade_gate":"BLOCKED",
               "completed":[{"index":0}]}
        starts=[rotating_start(7,i) for i in range(7)]
        self.assertEqual(len(set(starts)),7)
        selections=[choose(self.plan(),prior,start_index=start) for start in starts]
        self.assertTrue(any(1 not in group for group in selections))
        self.assertTrue(all(len(group)==4 and len(set(group))==4 for group in selections))

    def test_400_shard_rotation_covers_every_start(self):
        starts=[rotating_start(400,i) for i in range(400)]
        self.assertEqual(len(set(starts)),400)
        self.assertEqual(starts[:3],[0,399,398])
        self.assertNotEqual(rotating_start(400,0),rotating_start(400,100))

    def test_single_shard_pilot_cli_outputs_only_first(self):
        import json,os,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from collector.p1_quad_pick import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            plan=root/"plan.json"
            output=root/"outputs.txt"
            plan.write_text(json.dumps(self.plan()))
            args=["p1_quad_pick","--plan",str(plan),"--output-file",str(output)]
            with patch("sys.argv",args),patch.dict(os.environ,{"GITHUB_RUN_NUMBER":"0"}):
                main()
            recorded=dict(line.split("=",1) for line in output.read_text().splitlines())
            self.assertEqual(recorded["first"],"0000")
            self.assertEqual(recorded["has_first"],"true")
            for name in ("second","third","fourth"):
                self.assertEqual(recorded["has_"+name],"false")
                self.assertEqual(recorded[name],"NONE")

    def test_optional_two_shard_pilot_cli(self):
        import json,os,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from collector.p1_quad_pick import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan=root/"plan.json";out=root/"outputs.txt"
            plan.write_text(json.dumps(self.plan()))
            argv=["p1_quad_pick","--plan",str(plan),"--output-file",str(out),"--per-run","2"]
            with patch("sys.argv",argv),patch.dict(os.environ,{"GITHUB_RUN_NUMBER":"0"}):
                main()
            result=dict(line.split("=",1) for line in out.read_text().splitlines())
            self.assertEqual(result["first"],"0000")
            self.assertEqual(result["second"],"0001")
            self.assertEqual(result["has_second"],"true")
            self.assertEqual(result["has_third"],"false")
            for invalid in ("0","3"):
                with patch("sys.argv",argv[:-1]+[invalid]),patch.dict(os.environ,{"GITHUB_RUN_NUMBER":"0"}):
                    with self.assertRaises(SystemExit):main()

    def test_workflow_keeps_single_ordered_offline_and_vendor_steps(self):
        from pathlib import Path
        workflow=(Path(__file__).resolve().parents[1]/".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        required=(
            "      - name: Offline source tests",
            "      - name: Install free Baostock",
            "      - name: Observe current Beijing-date mainboard roster from free provider",
            "      - uses: actions/upload-artifact@v4",
        )
        positions=[workflow.index(item) for item in required]
        self.assertEqual(positions,sorted(positions))
        for item in required:
            self.assertEqual(workflow.count(item),1)
        self.assertNotIn("\n,text)",workflow)
        # Any opening heredoc must have a matching terminator, without assuming
        # the workflow contains a fixed number of Python scripts.
        opened=sum("<<'PY'" in line for line in workflow.splitlines())
        closed=sum(line.strip()=="PY" for line in workflow.splitlines())
        self.assertEqual(opened,closed)
        self.assertTrue(workflow.rstrip().endswith("if-no-files-found: warn"))

    def test_invalid_run_rotation_fails_closed(self):
        for value in (-1,True,"2"):
            with self.assertRaises(ValueError):
                rotating_start(7,value)

    def test_changed_epoch_fails(self):
        with self.assertRaises(ValueError):
            choose(self.plan(),{"source_sha256":"b"*64,"shard_count":7,
                                "trade_gate":"BLOCKED","completed":[]})
if __name__=="__main__":unittest.main()
