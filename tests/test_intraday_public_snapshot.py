"""Offline source schema, stale quote, symbol and no-trade tests."""
import datetime as dt,json,unittest
from zoneinfo import ZoneInfo
from collector.intraday_public_snapshot import parse_tencent,parse_eastmoney,quality

NOW=dt.datetime(2026,11,3,10,34,25,tzinfo=ZoneInfo("Asia/Shanghai"))
def quote(ts="20261103103418",code="002249",ratio="1.49"):
    f=[""]*55
    for k,v in {1:"大洋电机",2:code,3:"7.54",4:"7.36",6:"1113875",30:ts,49:ratio}.items():f[k]=v
    return 'v_sz'+code+'="'+'~'.join(f)+'";'
def minutes(day="2026-11-03"):
    return json.dumps({"rc":0,"data":{"code":"002249","trends":[
        f"{day} 10:33,7.47,7.47,7.48,7.45,100,74700,7.4",
        f"{day} 10:34,7.47,7.54,7.55,7.46,200,150000,7.5"]}})
class IntradaySnapshotTests(unittest.TestCase):
    def test_quote_fields_and_freshness(self):
        q=parse_tencent(quote(),"002249")
        self.assertEqual(q["price"],7.54)
        self.assertEqual(q["volume_ratio"],1.49)
        self.assertEqual(q["quote_time"],"2026-11-03T10:34:18+08:00")
    def test_reject_wrong_symbol(self):
        with self.assertRaises(ValueError):parse_tencent(quote(code="002696"),"002249")
    def test_reject_nonfinite_ratio(self):
        with self.assertRaises(ValueError):parse_tencent(quote(ratio="NaN"),"002249")
    def test_partial_minute_excluded(self):
        m=parse_eastmoney(minutes(),"002249",NOW)
        self.assertEqual(m["rows_today"],2)
        self.assertEqual(m["completed_minutes"],1)
        self.assertEqual(m["completed_minute_volume_lots"],100)
        self.assertFalse(m["minute_data_complete"])
    def test_wrong_day_and_duplicate_rejected(self):
        for bad in [minutes("2026-11-02"),minutes().replace("10:34","10:33")]:
            with self.subTest(data=bad[:30]):
                with self.assertRaises(ValueError):parse_eastmoney(bad,"002249",NOW)
    def test_gap_in_observed_minute_sequence_is_reported(self):
        raw=minutes().replace("10:34","10:35")
        m=parse_eastmoney(raw,"002249",NOW)
        self.assertIn("OBSERVED_MINUTE_GAPS",m["minute_validation_issues"])
        self.assertEqual(m["observed_gaps"][0]["minutes_missing"],1)
        q=parse_tencent(quote(),"002249")
        self.assertIn("OBSERVED_MINUTE_GAPS",quality(q,m,NOW)["validation_issues"])

    def test_lunch_break_is_not_a_false_minute_gap(self):
        raw=json.dumps({"rc":0,"data":{"code":"002249","trends":[
            "2026-11-03 11:30,7.47,7.47,7.48,7.45,100,74700,7.4",
            "2026-11-03 13:01,7.47,7.54,7.55,7.46,200,150000,7.5"]}})
        now=dt.datetime(2026,11,3,13,2,25,tzinfo=NOW.tzinfo)
        m=parse_eastmoney(raw,"002249",now)
        self.assertEqual(m["observed_gaps"],[])
        self.assertNotIn("OBSERVED_MINUTE_GAPS",m["minute_validation_issues"])

    def test_minutes_outside_session_flagged(self):
        raw=minutes().replace("10:33","12:33").replace("10:34","12:34")
        m=parse_eastmoney(raw,"002249",NOW)
        self.assertIn("OUTSIDE_CN_A_SHARE_SESSION",m["minute_validation_issues"])

    def test_volume_amount_unit_mismatch_flagged(self):
        raw=minutes().replace("100,74700","100,747")
        m=parse_eastmoney(raw,"002249",NOW)
        self.assertIn("VOLUME_AMOUNT_UNIT_MISMATCH",m["minute_validation_issues"])
        self.assertEqual(m["minute_unit"],"lots_100_shares")

    def test_no_trade_even_fresh(self):
        q=parse_tencent(quote(),"002249")
        m=parse_eastmoney(minutes(),"002249",NOW)
        result=quality(q,m,NOW)
        self.assertFalse(result["executable_quote"])
        self.assertIn("MINUTE_COMPLETENESS_UNVERIFIED",result["validation_issues"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])
    def test_stale_quote_is_rejected(self):
        q=parse_tencent(quote(ts="20261103103000"),"002249")
        m=parse_eastmoney(minutes(),"002249",NOW)
        self.assertIn("QUOTE_STALE_OR_FUTURE",quality(q,m,NOW)["validation_issues"])

if __name__=="__main__":unittest.main()
