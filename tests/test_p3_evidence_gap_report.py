"""CLI reports unfilled official-source slots truthfully."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from collector.p3_evidence_gap_report import main

class GapReportTests(unittest.TestCase):
    def test_empty_official_evidence_means_zero_verification(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            scope=root/"scope.json"; scope.write_text(json.dumps({"codes":["sh.600421"],"decision_dates":["2026-06-22"]}))
            evidence=root/"evidence.json";evidence.write_text("[]")
            out=root/"out.json"
            with patch("sys.argv",["report","--scope",str(scope),"--observations",str(evidence),"--out",str(out)]):
                report=main()
            self.assertEqual(report["coverage_ratio"],"0/4")
            self.assertEqual(report["missing_evidence_cells"],4)
            self.assertEqual(report["trade_gate"],"BLOCKED")
            self.assertFalse(report["scope_is_full_mainboard"])
    def test_unbounded_scope_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);scope=root/"scope.json"; scope.write_text(json.dumps({"codes":["sh.600421"],"decision_dates":[f"2026-01-{i:02d}" for i in range(1,33)]}))
            evidence=root/"evidence.json";evidence.write_text("[]")
            with patch("sys.argv",["report","--scope",str(scope),"--observations",str(evidence),"--out",str(root/"out.json")]):
                with self.assertRaisesRegex(ValueError,"cap exceeded"):
                    main()

if __name__=="__main__":
    unittest.main()
