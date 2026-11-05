"""Frozen acceptance totals cannot be adjusted to fake project progress."""
import copy
import json
import unittest
from pathlib import Path
from collector.progress_baseline import audit, TESTS

MANIFEST=json.loads(Path("progress_manifest.json").read_text())
SHA="a"*40

class ProgressBaselineTests(unittest.TestCase):
    def test_no_tests_no_claim(self):
        r=audit(Path("."),MANIFEST,SHA)
        self.assertFalse(r["tests_executed"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(set(r["stages"]),{"P2","P3","P4"})
        for phase in r["stages"].values():
            self.assertIsNone(phase["engineering_acceptance_baseline_pct"])
            self.assertEqual(len(phase["criteria"]),10)
            self.assertFalse(any(x["passed"] for x in phase["criteria"]))
            self.assertFalse(phase["formal_trading_ready"])
    def test_rejects_mutated_denominators_and_unsafe_claims(self):
        changes=(
            lambda x:x["phases"]["P2"].pop(),
            lambda x:x["phases"]["P4"][0].update(weight=100),
            lambda x:x["phases"]["P3"][0].update(id="fabricated"),
            lambda x:x.update(trade_gate="OPEN"),
            lambda x:x.update(historical_PIT_verified=True),
        )
        for change in changes:
            with self.subTest(change=change):
                m=copy.deepcopy(MANIFEST)
                change(m)
                with self.assertRaises(ValueError):
                    audit(Path("."),m,SHA)
    def test_only_explicit_independent_contracts_admitted(self):
        self.assertEqual({k: len(v) for k,v in TESTS.items()},
                         {"P2":3,"P3":3,"P4":5})
        for phase,contracts in TESTS.items():
            self.assertEqual(len(set(module for _,module in contracts.values())),len(contracts))
            self.assertTrue(set(contracts).issubset(
                {row["id"] for row in MANIFEST["phases"][phase]}))
        r=audit(Path("."),MANIFEST,SHA)
        self.assertTrue(all(all(not row["passed"] for row in stage["criteria"])
                            for stage in r["stages"].values()))
    def test_no_unpinned_ref(self):
        with self.assertRaises(ValueError):
            audit(Path("."),MANIFEST,"main")

if __name__=="__main__":
    unittest.main()
