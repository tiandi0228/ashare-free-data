"""Never promote research quotes or hypothetical prices to live A-share buy signals."""
import copy
import unittest

from collector.p2_signal_admission import assess


def snapshot():
    return {
        "phase":"P1_PUBLIC_INTRADAY_RESEARCH_SNAPSHOT",
        "asof":"2026-11-03T10:34:25+08:00",
        "provider_type":"UNOFFICIAL_WEB_ENDPOINTS",
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],
        "symbols":{
            "002249":{
                "quote":{
                    "code":"002249",
                    "price":10.0,
                    "quote_time":"2026-11-03T10:34:18+08:00",
                },
                "checked_at":"2026-11-03T10:34:25+08:00",
                "validation":{
                    "status":"RESEARCH_ONLY",
                    "trade_gate":"BLOCKED",
                    "executable_quote":False,
                    "cross_source_price_verified":False,
                    "quote_age_seconds":7,
                    "validation_issues":[],
                },
                "cross_source_diagnostic":{
                    "status":"RESEARCH_PRICE_PROXIMITY_ONLY",
                    "trade_gate":"BLOCKED",
                    "cross_source_price_verified":False,
                    "executable_quote":False,
                    "absolute_difference_cny":"0.00",
                },
            }
        }
    }


def plan():
    return [{"code":"002249","is_st":False,"halted":False,
             "holding_days":3,"capital_cny":"8000",
             "entry":"10.00","stop":"9.80","target":"10.60"}]


class SignalAdmissionTests(unittest.TestCase):
    def test_perfectly_matching_research_quotes_still_blocked(self):
        x=assess(snapshot(),plan())
        self.assertEqual(x["state"],"BLOCKED")
        self.assertFalse(x["buy_recommendations_authorized"])
        self.assertFalse(x["realtime_execution_checks_verified"])
        self.assertEqual(x["orders"],[])
        self.assertEqual(x["executable_signal_count"],0)
        row=x["symbols"]["002249"]
        self.assertEqual(row["admission"],"RESEARCH_ONLY_NOT_ACTIONABLE")
        self.assertIn("SIMULTANEOUS_EXECUTABLE_QUOTES_NOT_VERIFIED",row["reasons"])
        self.assertEqual(row["hypothetical_risk"]["status"],
                         "MATHEMATICALLY_FEASIBLE_NOT_EXECUTABLE")
        self.assertEqual(row["orders"],[])

    def test_without_plan_still_records_research_reason(self):
        x=assess(snapshot())
        self.assertEqual(x["evaluated_symbols"],1)
        self.assertIn("NO_HYPOTHETICAL_RISK_PLAN",
                      x["symbols"]["002249"]["reasons"])
        self.assertIsNone(x["symbols"]["002249"]["hypothetical_risk"])

    def test_stale_quote_and_bad_clock_are_not_actionable(self):
        x=snapshot()
        x["symbols"]["002249"]["quote"]["quote_time"]="2026-11-03T10:33:00+08:00"
        self.assertIn("QUOTE_EXCEEDS_15S_WINDOW",
                      assess(x)["symbols"]["002249"]["reasons"])
        x=snapshot()
        x["symbols"]["002249"]["checked_at"]="2026-11-03T10:34:25"
        self.assertIn("SOURCE_CLOCK_INVALID",
                      assess(x)["symbols"]["002249"]["reasons"])

    def test_missing_source_and_price_disagreement_do_not_promote(self):
        x=snapshot()
        x["symbols"]["002249"]={"status":"SOURCE_UNAVAILABLE"}
        reasons=assess(x)["symbols"]["002249"]["reasons"]
        self.assertIn("SOURCE_UNAVAILABLE",reasons)
        self.assertIn("QUOTE_QUALITY_UNVERIFIED",reasons)
        x=snapshot()
        x["symbols"]["002249"]["cross_source_diagnostic"]["status"]="NOT_COMPARABLE"
        reasons=assess(x)["symbols"]["002249"]["reasons"]
        self.assertIn("CROSS_SOURCE_NOT_COMPARABLE",reasons)

    def test_chinext_would_be_excluded_even_if_present(self):
        x=snapshot()
        row=x["symbols"].pop("002249")
        row["quote"]["code"]="300015"
        x["symbols"]["300015"]=row
        self.assertIn("OUTSIDE_SHENZHEN_SHANGHAI_MAINBOARD",
                      assess(x)["symbols"]["300015"]["reasons"])

    def test_risk_plan_without_st_confirmation_rejected(self):
        p=plan()
        p[0]["is_st"]=None
        x=assess(snapshot(),p)
        self.assertIn("HYPOTHETICAL_RISK_PLAN_REJECTED",
                      x["symbols"]["002249"]["reasons"])

    def test_duplicate_or_unseen_plans_fail_closed(self):
        self.assertEqual(assess(snapshot(),plan()*2)["reason"],
                         "DUPLICATE_HYPOTHETICAL_PLAN")
        p=plan()
        p[0]["code"]="600000"
        self.assertEqual(assess(snapshot(),p)["reason"],
                         "PLAN_SYMBOL_ABSENT_FROM_SNAPSHOT")

    def test_unsafe_or_malformed_upstream_snapshot_rejected(self):
        for changes in (
            {"trade_gate":"OPEN"},
            {"orders":[{"side":"BUY"}]},
            {"provider_type":"VERIFIED_EXCHANGE"},
            {"asof":"2026-11-03T10:34:25"},
        ):
            with self.subTest(changes=changes):
                x=snapshot();x.update(changes)
                result=assess(x)
                self.assertEqual(result["trade_gate"],"BLOCKED")
                self.assertEqual(result["orders"],[])
                self.assertEqual(result["executable_candidates"],[])
                self.assertEqual(result["state"],"BLOCKED")

    def test_unbounded_or_invalid_records_fail_closed(self):
        self.assertEqual(assess(None)["reason"],"SOURCE_SNAPSHOT_INVALID")
        x=snapshot();x["symbols"]=dict.fromkeys(
            ("002249","002696","600000","600001","600002","600003"),{})
        self.assertEqual(assess(x)["reason"],"UNBOUNDED_RESEARCH_SNAPSHOT")


if __name__=="__main__":
    unittest.main()
