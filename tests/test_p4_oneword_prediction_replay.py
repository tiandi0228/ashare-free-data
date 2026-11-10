import copy
import unittest

from collector.p4_oneword_prediction_replay import RULE, assess


def case():
    return {
        "issuer": "sz.000069",
        "predicted_on": "2026-11-10",
        "session_on": "2026-11-11",
        "prediction": "ONE_WORD_LIMIT_UP",
        "prediction_rule": RULE,
        "trade_gate": "BLOCKED", "orders": [],
    }


def observation():
    return {
        "session_on": "2026-11-11",
        "previous_close": "1.70",
        "open": "1.87", "high": "1.87",
        "low": "1.87", "close": "1.87",
        "exchange_limit_up_price": "1.87",
        "complete_session": True,
        "original_exchange_ticks_authenticated": False,
        "official_limit_price_authenticated": False,
        "source_ref": "https://example.test/exchange",
        "source_sha256": "a"*64,
    }


class OneWordPredictionReplayTests(unittest.TestCase):
    def test_forecast_without_next_session_is_unresolved(self):
        result = assess(case())
        self.assertEqual(result["audit_state"], "UNRESOLVED_NO_INDEPENDENT_SESSION_EVIDENCE")
        self.assertFalse(result["actual_one_word_limit_up_certified"])
        self.assertEqual(result["issuer"], "sz.000069")
        self.assertEqual(result["trade_gate"], "BLOCKED")
        self.assertEqual(result["orders"], [])

    def test_daily_ohlc_matching_limit_not_proof_of_oneword(self):
        data=case()
        data["observation"]=observation()
        result=assess(data)
        self.assertEqual(result["audit_state"], "DAILY_OHLC_COMPATIBLE_NOT_CERTIFIED_ONE_WORD")
        self.assertTrue(result["observation"]["daily_ohlc_matches_one_word_pattern"])
        self.assertFalse(result["forecast_accuracy_claimed"])
        self.assertFalse(result["prediction_observation_independently_replayed"])

    def test_completed_low_below_limit_falsifies_claimed_pattern(self):
        data=case()
        data["observation"]=observation()
        data["observation"]["low"]="1.82"
        self.assertEqual(assess(data)["audit_state"], "FALSIFIED_BY_DAILY_COMPLETED_OHLC_CLAIM")
        data["observation"]["low"]="1.83"
        data["observation"]["open"]="1.83"
        self.assertEqual(assess(data)["audit_state"], "FALSIFIED_BY_DAILY_COMPLETED_OHLC_CLAIM")

    def test_partial_session_does_not_certify_or_refute(self):
        data=case()
        data["observation"]=observation()
        data["observation"]["complete_session"]=False
        data["observation"]["low"]="1.81"
        self.assertEqual(assess(data)["audit_state"], "UNRESOLVED_PARTIAL_SESSION_OBSERVATION")

    def test_forecast_temporal_order_and_universe(self):
        data=case()
        data["predicted_on"]="2026-11-11"
        with self.assertRaisesRegex(ValueError, "precede"):
            assess(data)
        data=case()
        data["issuer"]="sz.300015"
        with self.assertRaisesRegex(ValueError, "nonmainboard"):
            assess(data)

    def test_no_fake_future_or_trade_authorization(self):
        data=case()
        data["prediction"]="RALLY_EXPECTED"
        with self.assertRaisesRegex(ValueError, "unsupported prediction"):
            assess(data)
        data=case()
        data["orders"]=[{"side":"BUY"}]
        with self.assertRaisesRegex(ValueError, "executable order"):
            assess(data)

    def test_reject_ohlc_limit_and_source_anomalies(self):
        for key,value in (
            ("high", "1.85"),
            ("high", "1.90"),
            ("low", "NaN"),
            ("exchange_limit_up_price", "1.86"),
            ("source_sha256", "fake"),
            ("session_on", "2026-11-12"),
        ):
            data=case()
            data["observation"]=observation()
            data["observation"][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):
                assess(data)

    def test_claimed_authentication_is_not_independent_replay(self):
        data=case()
        data["observation"]=observation()
        data["observation"]["original_exchange_ticks_authenticated"]=True
        data["observation"]["official_limit_price_authenticated"]=True
        result=assess(data)
        self.assertFalse(result["actual_one_word_limit_up_certified"])
        self.assertFalse(result["official_limit_price_verified_by_this_module"])
        self.assertEqual(result["trade_gate"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
