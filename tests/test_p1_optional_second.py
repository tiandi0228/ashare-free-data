import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.p1_optional_second import decide, main


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

    def test_cli_outputs_effective_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"output.txt"
            report=Path(tmp)/"second.json"
            args=["p1_optional_second",
                  "--requested-second","true","--outcome","failure",
                  "--second","0032","--output-file",str(out),
                  "--report",str(report)]
            with patch("sys.argv",args):
                main()
            self.assertEqual(out.read_text(),"has_second=false\n")
            recorded=json.loads(report.read_text())
            self.assertEqual(recorded["effective_shard_count"],1)
            self.assertEqual(recorded["status"],"SECOND_FAILED_PRESERVE_FIRST")


if __name__ == "__main__":
    unittest.main()
