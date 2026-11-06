import unittest
from decimal import Decimal
from collector.tencent_baostock_daily_compare import (
    expected_m5_labels,utcday_groups,compare,parse_baostock,FIELDS
)
from collector.tencent_eight_sample_pilot import MINUTE_SYMBOLS
import json

def fixture_rows(date="20261105", missing=False):
    stamps=sorted(expected_m5_labels(f"{date[:4]}-{date[4:6]}-{date[6:]}"))
    if missing:stamps.pop(10)
    return [[t,"10","10.1","10.2","9.9","100"] for t in stamps]

def raw(sym,rows):
    return json.dumps({"code":0,"data":{sym:{"m5":rows}}}).encode()

def daily(sym,day="2026-11-05"):
    row=dict(zip(FIELDS,[day,sym[:2]+"."+sym[2:],"10","10.2","9.9","10.1",
                          "10000","100000","3","1"]))
    return parse_baostock([row],sym)

class CompareTests(unittest.TestCase):
    def test_canonical_labels_are_48(self):
        q=expected_m5_labels("2026-11-05")
        self.assertEqual(len(q),48)
        self.assertIn("202611051130",q)
        self.assertIn("202611051305",q)
        self.assertIn("202611051500",q)

    def test_complete_day_ohlc_matches(self):
        t={s:utcday_groups(raw(s,fixture_rows()),s) for s in MINUTE_SYMBOLS}
        b={s:daily(s) for s in MINUTE_SYMBOLS}
        r=compare(t,b)
        self.assertEqual(r["comparable_days"],2)
        self.assertEqual(r["within_tick_days"],2)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertFalse(r["volume_comparison_performed"])

    def test_missing_bar_is_not_a_full_day(self):
        t={s:utcday_groups(raw(s,fixture_rows(missing=True)),s) for s in MINUTE_SYMBOLS}
        r=compare(t,{s:daily(s) for s in MINUTE_SYMBOLS})
        self.assertEqual(r["comparable_days"],0)
        self.assertTrue(all(x["comparison"].startswith("NOT_COMPARABLE") for x in r["comparison_records"]))

    def test_ohlc_disagreement_not_hidden(self):
        t={s:utcday_groups(raw(s,fixture_rows()),s) for s in MINUTE_SYMBOLS}
        b={s:daily(s) for s in MINUTE_SYMBOLS}
        b[MINUTE_SYMBOLS[0]]["2026-11-05"]["close"]="11"
        r=compare(t,b)
        self.assertEqual(r["disagreement_days"],1)
        self.assertFalse(r["independent_source_consistency_certified"])

    def test_baostock_adjustment_and_symbol_gates(self):
        row=dict(zip(FIELDS,["2026-11-05","sh.600519","10","10.2","9.9","10.1",
                             "100","1000","2","1"]))
        with self.assertRaises(ValueError):
            parse_baostock([row],"sh600519")
        row["adjustflag"]="3"
        with self.assertRaises(ValueError):
            parse_baostock([row],"sz002249")

if __name__=="__main__":unittest.main()
