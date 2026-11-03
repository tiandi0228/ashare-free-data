"""Never certify a live cross-source quote from an unrelated minute bar."""
import unittest
from collector.intraday_cross_source_audit import evaluate

def q(**kwargs):
    return dict(price=7.54,quote_time="2026-11-03T10:34:20+08:00",**kwargs)
def m(**kwargs):
    return dict(last_completed_minute_time="2026-11-03T10:33:00+08:00",
                last_completed_minute_close=7.54,minute_validation_issues=[],**kwargs)
NOW="2026-11-03T10:34:25+08:00"
class CrossSourceTests(unittest.TestCase):
    def test_equal_prices_never_certify_executable_quotes(self):
        x=evaluate(q(),m(),NOW)
        self.assertEqual(x["status"],"RESEARCH_PRICE_PROXIMITY_ONLY")
        self.assertEqual(x["absolute_difference_cny"],"0.00")
        self.assertFalse(x["cross_source_price_verified"])
        self.assertFalse(x["executable_quote"])
        self.assertEqual(x["trade_gate"],"BLOCKED")
        self.assertEqual(x["orders"],[])
    def test_price_disagreement_measured_not_hidden(self):
        mm=m();mm["last_completed_minute_close"]=7.40
        x=evaluate(q(),mm,NOW)
        self.assertEqual(x["status"],"RESEARCH_PRICE_PROXIMITY_ONLY")
        self.assertFalse(x["observed_within_one_tick"])
        self.assertFalse(x["cross_source_price_verified"])
    def test_stale_quote_rejected(self):
        qq=q();qq["quote_time"]="2026-11-03T10:33:00+08:00"
        self.assertEqual(evaluate(qq,m(),NOW)["reason"],"QUOTE_STALE_OR_FUTURE")
    def test_future_bar_rejected(self):
        mm=m();mm["last_completed_minute_time"]="2026-11-03T10:34:00+08:00"
        self.assertEqual(evaluate(q(),mm,NOW)["reason"],"MINUTE_BAR_NOT_COMPLETED")
    def test_mismatched_day_rejected(self):
        mm=m();mm["last_completed_minute_time"]="2026-11-02T10:33:00+08:00"
        self.assertEqual(evaluate(q(),mm,NOW)["reason"],"DIFFERENT_TRADING_DAYS")
    def test_bad_minute_quality_rejected(self):
        mm=m();mm["minute_validation_issues"]=["OBSERVED_MINUTE_GAPS"]
        self.assertEqual(evaluate(q(),mm,NOW)["reason"],"MINUTE_VALIDATION_ISSUES_PRESENT")
    def test_missing_values_block(self):
        mm=m();mm["last_completed_minute_close"]=None
        self.assertEqual(evaluate(q(),mm,NOW)["status"],"NOT_COMPARABLE")
    def test_no_sources_block(self):
        x=evaluate(None,m(),NOW)
        self.assertEqual(x["status"],"NOT_COMPARABLE")
        self.assertEqual(x["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
