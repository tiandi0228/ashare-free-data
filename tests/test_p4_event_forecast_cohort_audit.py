import copy
import unittest

from collector.p4_event_forecast_cohort_audit import assess
from collector.p4_oneword_prediction_replay import RULE


def entry(code, date, state, observation=True):
    return {
        "issuer": code,
        "predicted_on": "2026-11-10",
        "session_on": date,
        "prediction": "ONE_WORD_LIMIT_UP",
        "prediction_rule": RULE,
        "prediction_sha256": "a"*64,
        "observation_sha256": "b"*64 if observation else None,
        "audit_state": state,
        "independent_external_source_authenticated": False,
        "prediction_pre_event_timestamp_authenticated": False,
        "trade_gate": "BLOCKED",
        "orders": [],
    }


def sample():
    return {"asof": "2026-11-12", "forecasts": [
        entry("sz.000069", "2026-11-11",
              "MINUTE_BARS_COMPATIBLE_ONE_WORD_NOT_CERTIFIED"),
        entry("sz.000058", "2026-11-11",
              "CONTRADICTED_BY_LOCALLY_REPLAYED_MINUTE_LOW"),
        entry("sz.000011", "2026-11-13",
              "UNRESOLVED_NO_INDEPENDENT_SESSION_EVIDENCE", False),
    ]}


class CohortForecastAuditTests(unittest.TestCase):
    def test_unverified_compatible_not_counted_as_hit(self):
        report = assess(sample())
        self.assertEqual(report["submitted_forecasts"],3)
        self.assertEqual(report["unresolved"],1)
        self.assertEqual(report["locally_compatible_unverified"],1)
        self.assertEqual(report["locally_contradicted_unverified"],1)
        self.assertIsNone(report["hit_rate"])
        self.assertEqual(report["verified_successes"],0)
        self.assertEqual(report["independently_verified_forecast_sample_size"],0)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])

    def test_duplicate_per_symbol_session_forbidden(self):
        p=sample()
        p["forecasts"].append(copy.deepcopy(p["forecasts"][0]))
        with self.assertRaisesRegex(ValueError,"duplicated"):
            assess(p)

    def test_future_outcome_forbidden_but_pending_allowed(self):
        p=sample()
        p["forecasts"][2]["observation_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"unobserved"):
            assess(p)
        p=sample()
        p["forecasts"][2]["audit_state"]="DAILY_OHLC_COMPATIBLE_NOT_CERTIFIED_ONE_WORD"
        p["forecasts"][2]["observation_sha256"]="b"*64
        with self.assertRaisesRegex(ValueError,"future-session"):
            assess(p)

    def test_unsupported_pre_event_authentication_flag_fails_closed(self):
        for field in ("independent_external_source_authenticated",
                      "prediction_pre_event_timestamp_authenticated"):
            p=sample()
            p["forecasts"][0][field]=True
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,"self-asserted"):
                assess(p)

    def test_unsupported_issuer_predictions_and_state_rejected(self):
        for field, value in (
            ("issuer","sz.300015"),
            ("predicted_on","2026-11-11"),
            ("prediction","UP_TOMORROW"),
            ("prediction_rule","LOOSE"),
            ("audit_state","CERTIFIED_HIT"),
            ("prediction_sha256","bad"),
            ("observation_sha256","bad"),
        ):
            p=sample()
            p["forecasts"][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                assess(p)

    def test_never_approve_orders_or_trades(self):
        p=sample()
        p["forecasts"][0]["orders"]=[{"side":"BUY"}]
        with self.assertRaisesRegex(ValueError,"executable order"):
            assess(p)

    def test_empty_cohort_does_not_invent_success_rate(self):
        r=assess({"asof":"2026-11-10","forecasts":[]})
        self.assertEqual(r["submitted_forecasts"],0)
        self.assertIsNone(r["hit_rate"])
        self.assertFalse(r["immutable_pre_event_forecasts_authenticated"])


if __name__ == "__main__":
    unittest.main()
