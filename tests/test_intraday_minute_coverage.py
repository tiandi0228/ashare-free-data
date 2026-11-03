"""Audit label coverage conservatively; never certify execution readiness."""
import datetime as dt,json,unittest
from zoneinfo import ZoneInfo
from collector.intraday_minute_coverage import audit_minute_coverage,expected_minute_labels
from collector.intraday_public_snapshot import parse_eastmoney,quality,parse_tencent
from tests.test_intraday_public_snapshot import quote

TZ=ZoneInfo("Asia/Shanghai")
def at(h,m,s=25):
    return dt.datetime(2026,11,3,h,m,s,tzinfo=TZ)
def feed(*times):
    return json.dumps({"rc":0,"data":{"code":"002249","trends":[
        f"2026-11-03 {t},7.47,7.47,7.48,7.45,100,74700,7.4" for t in times]}})

class CoverageTests(unittest.TestCase):
    def test_morning_open_expected_labels(self):
        expected=expected_minute_labels(at(9,30).date(),at(9,31))
        self.assertEqual(len(expected),1)
        self.assertEqual(expected[0].strftime("%H:%M"),"09:30")
    def test_lunch_has_no_expected_labels(self):
        self.assertEqual(len(expected_minute_labels(at(12,10).date(),at(12,10))),121)
    def test_afternoon_expected_labels_and_close(self):
        self.assertEqual(len(expected_minute_labels(at(13,45).date(),at(13,45))),166)
        self.assertEqual(len(expected_minute_labels(at(15,5).date(),at(15,5))),242)
    def test_future_minute_is_not_completed(self):
        now=at(13,44)
        c=audit_minute_coverage([at(13,43,0),at(13,45,0)],now)
        self.assertEqual(c["future_labels"],["2026-11-03T13:45:00+08:00"])
        self.assertEqual(c["covered_expected_completed_labels"],1)
        self.assertEqual(c["missing_expected_completed_labels"],164)
        self.assertFalse(c["minute_data_complete_certified"])
    def test_morning_missing_open_detected(self):
        now=at(9,34)
        c=audit_minute_coverage([at(9,33,0)],now)
        self.assertEqual(c["expected_completed_labels"],4)
        self.assertEqual(c["missing_expected_completed_labels"],3)
        self.assertEqual(c["coverage_ratio_observed"],0.25)
    def test_complete_assumed_grid_still_not_certified(self):
        now=at(9,33)
        stamps=[at(9,m,0) for m in (30,31,32)]
        c=audit_minute_coverage(stamps,now)
        self.assertEqual(c["coverage_ratio_observed"],1)
        self.assertFalse(c["minute_data_complete_certified"])
    def test_integrated_parser_flags_missing_future(self):
        now=at(13,44)
        m=parse_eastmoney(feed("13:43","13:45"),"002249",now)
        cov=m["expected_minute_coverage"]
        self.assertIn("OBSERVED_FUTURE_MINUTE_LABEL",m["minute_validation_issues"])
        self.assertIn("EXPECTED_COMPLETED_MINUTES_MISSING",m["minute_validation_issues"])
        self.assertFalse(m["minute_data_complete"])
        q=parse_tencent(quote(ts="20261103134418"),"002249")
        result=quality(q,m,now)
        self.assertFalse(result["executable_quote"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertIn("OBSERVED_FUTURE_MINUTE_LABEL",result["validation_issues"])
    def test_empty_and_naive_clock_rejected(self):
        with self.assertRaises(ValueError):audit_minute_coverage([],at(13,44))
        with self.assertRaises(ValueError):
            expected_minute_labels(at(13,44).date(),dt.datetime(2026,11,3,13,44))
if __name__=="__main__":unittest.main()
