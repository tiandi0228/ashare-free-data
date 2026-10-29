import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.p1_optional_second import decide, main, accept_verified_second, verify_second_capture


class OptionalSecondTests(unittest.TestCase):
    def test_first_only_is_consistently_recorded(self):
        item = decide("false", "skipped", "NONE")
        self.assertEqual(item["effective_shard_count"], 1)
        self.assertFalse(item["accepted_second"])
        self.assertEqual(item["trade_gate"], "BLOCKED")

    def test_successful_optional_second_is_accepted(self):
        item = decide("true", "success", "0032")
        self.assertEqual(item["status"], "SECOND_SHARD_CAPTURED")
        self.assertEqual(item["second_shard_index"], 32)
        self.assertEqual(item["effective_shard_count"], 2)

    def test_failed_optional_second_preserves_first(self):
        item = decide("true", "failure", "0032")
        self.assertEqual(item["status"], "SECOND_FAILED_PRESERVE_FIRST")
        self.assertEqual(item["effective_shard_count"], 1)
        self.assertFalse(item["accepted_second"])
        self.assertFalse(item["historical_PIT_verified"])
        self.assertEqual(item["orders"], [])
        self.assertEqual(item["executable_candidates"], [])

    def test_skipped_requested_second_is_not_silent_success(self):
        for args in (("true","skipped","0032"),
                     ("false","success","NONE"),
                     ("false","failure","NONE"),
                     ("true","failure","NONE"),
                     ("true","success","invalid")):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    decide(*args)

    def test_workflow_wires_effective_second_to_all_downstream_consumers(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/p1-fresh-vendor-roster.yml").read_text()
        start = workflow.index("      - name: Fetch next real roster shard historical bars")
        accept = workflow.index("      - name: Accept successful optional second shard")
        downstream = workflow[workflow.index(
            "      - name: Capture third eight-issuer frozen P1 shard", accept):]
        self.assertIn("id: second_fetch", workflow[start:accept])
        self.assertIn("continue-on-error: true", workflow[start:accept])
        self.assertIn("id: optional_second", workflow[accept:accept+500])
        self.assertIn("steps.second_fetch.outcome", workflow[accept:accept+600])
        self.assertNotIn("steps.pick.outputs.has_second", downstream)
        self.assertGreaterEqual(
            downstream.count("steps.optional_second.outputs.has_second"), 4)

    def test_verified_second_is_accepted_after_independent_replay(self):
        result=decide("true","success","0032")
        validated={"verified_shards":1,"verified_issuers":8,
                   "trade_gate":"BLOCKED","historical_PIT_verified":False}
        with patch("collector.p1_optional_second.verify_second_capture",return_value=validated) as verify:
            output=accept_verified_second(result,"plan.json","shards","second")
        verify.assert_called_once_with("plan.json","shards",32,"second")
        self.assertEqual(output["effective_shard_count"],2)
        self.assertEqual(output["second_verified_issuers"],8)
        self.assertEqual(output["status"],"SECOND_SHARD_VERIFIED")

    def test_bad_second_receipt_preserves_first_even_on_command_success(self):
        result=decide("true","success","0032")
        with patch("collector.p1_optional_second.verify_second_capture",
                   side_effect=ValueError("original CSV SHA mismatch")):
            output=accept_verified_second(result,"plan.json","shards","second")
        self.assertEqual(output["effective_shard_count"],1)
        self.assertFalse(output["accepted_second"])
        self.assertFalse(output["second_verification_passed"])
        self.assertEqual(output["second_rejection_type"],"ValueError")
        self.assertEqual(output["status"],"SECOND_INVALID_PRESERVE_FIRST")
        self.assertEqual(output["trade_gate"],"BLOCKED")

    def test_independent_replay_rejects_invalid_second_archive_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            plan=root/"plan.json"
            plan.write_text(json.dumps({
                "phase":"P1_FRESH_VENDOR_SHARD_PLAN","trade_gate":"BLOCKED",
                "historical_PIT_verified":False,
                "source_sha256":"a"*64,"shard_count":1,
                "shards":[{"index":0,"count":1,"name":"shard_0000.txt",
                           "sha256":"b"*64}]}))
            manifest=root/"shards";manifest.mkdir()
            (manifest/"shard_0000.txt").write_text("sh.600000\\n")
            with self.assertRaisesRegex(ValueError,"manifest digest"):
                verify_second_capture(plan,manifest,0,root/"second")

    def test_cli_outputs_effective_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"output.txt"
            report=Path(tmp)/"second.json"
            args=["p1_optional_second",
                  "--requested-second","true","--outcome","failure",
                  "--second","0032","--plan","plan.json",
                  "--manifest-root","shards","--second-folder","second",
                  "--output-file",str(out),
                  "--report",str(report)]
            with patch("sys.argv",args):
                main()
            self.assertEqual(out.read_text(),"has_second=false\n")
            recorded=json.loads(report.read_text())
            self.assertEqual(recorded["effective_shard_count"],1)
            self.assertEqual(recorded["status"],"SECOND_FAILED_PRESERVE_FIRST")


if __name__ == "__main__":
    unittest.main()
