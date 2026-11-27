import unittest
from collector.p4_official_limit_queue import build
class QueueTests(unittest.TestCase):
    def source(self):
        base=dict(asof="2026-11-25",source_artifact_sha256="a"*64,trade_gate="BLOCKED",orders=[],executable_candidates=[],historical_PIT_verified=False,official_limit_certified=0)
        r=dict(base,counts={"hypothetical_band_matches":1},records=[dict(code="sh.600001",day="2026-11-24",prior_day="2026-11-23",extension_sha256="b"*64,hypotheses=[dict(side="UP",assumed_band_pct="10.00")])])
        d=dict(code="sh.600001",signal_day="2026-11-23",entry_day="2026-11-24",exit_day="2026-11-25",horizon_sessions=3,any_flagged_window_days=["2026-11-24"],entry_up_hypothesis=True,exit_down_hypothesis=False)
        group=dict(details=[d],counts=dict(any_window_hypothesis=1,entry_up_hypotheses=1,exit_down_hypotheses=0,directional_risk_observations=1))
        j=dict(base,fixed_horizons=group,variant_a=dict(details=[dict(d,horizon_sessions=None)],counts=dict(group["counts"])))
        return r,j
    def test_deduplicate_across_strategies(self):
        r,j=self.source();x=build(r,j)
        self.assertEqual(x["unique_issuer_dates"],1);self.assertEqual(x["tasks"][0]["entry_exposure"],2)
        self.assertEqual(x["priority_counts"],{"P1_DIRECTIONAL":1});self.assertEqual(x["orders"],[])
    def test_count_mismatch(self):
        r,j=self.source();j["fixed_horizons"]["counts"]["entry_up_hypotheses"]=2
        with self.assertRaises(ValueError):build(r,j)
    def test_direction_mismatch(self):
        r,j=self.source();r["records"][0]["hypotheses"][0]["side"]="DOWN"
        with self.assertRaises(ValueError):build(r,j)
    def test_duplicate_risk(self):
        r,j=self.source();r["records"]*=2
        with self.assertRaises(ValueError):build(r,j)
