"""Prospective P4 fingerprints cannot authorize retrospective trades."""
import unittest
from collector.p4_prospective_protocol_freeze import freeze

BASE = dict(
    source_commit="a" * 40, baseline_artifact_sha256="b" * 64,
    created_at_utc="2026-11-11T09:00:00Z",
    window_start="2026-12-01", window_end="2027-02-01",
    strategy_id="MA20_COMPLETED_SIGNAL_V1",
    strategy_rules={
        "signal_rule": "COMPLETED_CLOSE_CROSSES_ABOVE_MA20",
        "entry_rule": "NEXT_VENDOR_OPEN_PROXY_NOT_FILL",
        "stop_fraction": "0.02", "target_fraction": "0.05",
        "min_holding_sessions": 3, "max_holding_sessions": 5,
        "friday_exit_rule": "FRIDAY_FORCE_EXIT_RESEARCH_ONLY",
        "same_day_sale_allowed": False,
    },
    fee_model={
        "commission_rate":"0.0002854", "commission_min_cny":"5",
        "sell_stamp_rate":"0.0005", "slippage_bps_each_side":"10",
        "capital_cny":"8000", "maximum_net_loss_fraction":"0.03",
        "minimum_net_reward_risk":"2",
    },
)

class ProtocolFreezeTests(unittest.TestCase):
    def test_stable_candidate_stays_blocked(self):
        a, b = freeze(**BASE), freeze(**BASE)
        self.assertEqual(a["status"], "CANDIDATE_FINGERPRINT_ONLY_NOT_OOS")
        self.assertEqual(a["candidate_sha256"], b["candidate_sha256"])
        self.assertFalse(a["historical_OOS_validated"])
        self.assertFalse(a["prospective_freeze_externally_attested"])
        self.assertFalse(a["trade_authorized"])
        self.assertEqual(a["trade_gate"], "BLOCKED")
        self.assertEqual(a["orders"], [])

    def test_changed_costs_change_fingerprint(self):
        x = dict(BASE["fee_model"], commission_min_cny="6")
        self.assertNotEqual(freeze(**BASE)["candidate_sha256"],
                            freeze(**dict(BASE, fee_model=x))["candidate_sha256"])

    def test_all_strategy_inputs_change_fingerprint(self):
        baseline = freeze(**BASE)["candidate_sha256"]
        for field, new_value in (
            ("stop_fraction", "0.025"), ("target_fraction", "0.08"),
            ("min_holding_sessions", 2), ("max_holding_sessions", 4),
        ):
            rules = dict(BASE["strategy_rules"], **{field: new_value})
            with self.subTest(field=field):
                altered = freeze(**dict(BASE, strategy_rules=rules))
                self.assertEqual(altered["status"], "CANDIDATE_FINGERPRINT_ONLY_NOT_OOS")
                self.assertNotEqual(altered["candidate_sha256"], baseline)

    def test_missing_or_unsafe_trade_rules_rejected(self):
        for rules in (
            None,
            {k: v for k, v in BASE["strategy_rules"].items() if k != "entry_rule"},
            dict(BASE["strategy_rules"], same_day_sale_allowed=True),
            dict(BASE["strategy_rules"], min_holding_sessions=True),
            dict(BASE["strategy_rules"], target_fraction="0"),
            dict(BASE["strategy_rules"], signal_rule="USE_FUTURE_CLOSE"),
        ):
            with self.subTest(rules=rules):
                result = freeze(**dict(BASE, strategy_rules=rules))
                self.assertEqual(result["status"], "REJECTED")
                self.assertEqual(result["orders"], [])
                self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_retrospective_and_same_day_refused(self):
        for day in ("2026-10-01", "2026-11-11"):
            with self.subTest(day=day):
                x = freeze(**dict(BASE, window_start=day))
                self.assertEqual(x["status"], "REJECTED")
                self.assertEqual(x["trade_gate"], "BLOCKED")

    def test_invalid_inputs_fail_closed(self):
        for changes in (
            {"source_commit":"main"}, {"baseline_artifact_sha256":"bad"},
            {"strategy_id":"unfrozen"}, {"created_at_utc":"2026-11-11T09:00:00+08:00"},
            {"window_end":"2026-02-30"},
            {"fee_model":dict(BASE["fee_model"], capital_cny="-100")},
            {"fee_model":dict(BASE["fee_model"], unexpected="1")},
        ):
            with self.subTest(changes=changes):
                x = freeze(**dict(BASE, **changes))
                self.assertEqual(x["status"], "REJECTED")
                self.assertEqual(x["orders"], [])

if __name__ == "__main__":
    unittest.main()
