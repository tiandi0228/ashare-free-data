"""Offline fail-closed tests of bounded historical 1m sampling."""
import json
import tempfile
import unittest
from pathlib import Path
from collector.eastmoney_m1_historical_probe import DAYS,SYMBOLS,expected,parse,run,url

def source(symbol,day,full=True):
    market=1 if symbol.startswith("sh") else 0
    stamps=sorted(expected(day))
    if not full:stamps=stamps[:10]
    rows=[f"{t[:4]}-{t[4:6]}-{t[6:8]} {t[8:10]}:{t[10:]},10,10.1,10.2,9.9,100" for t in stamps]
    return json.dumps({"rc":0,"data":{"code":symbol[2:],
        "market":market,"klines":rows}}).encode()

class HistoricalMinuteTests(unittest.TestCase):
    def test_exact_date_and_budget(self):
        self.assertEqual(len(expected(DAYS[0])),240)
        self.assertIn("klt=1",url(SYMBOLS[0],DAYS[0]))
        self.assertIn("beg=20261102&end=20261102",url(SYMBOLS[0],DAYS[0]))
        with self.assertRaises(ValueError):url("sz300015",DAYS[0])
    def test_full_and_partial(self):
        self.assertTrue(parse(source(SYMBOLS[0],DAYS[0]),SYMBOLS[0],DAYS[0])["full_requested_day_coverage"])
        p=parse(source(SYMBOLS[0],DAYS[0],False),SYMBOLS[0],DAYS[0])
        self.assertFalse(p["full_requested_day_coverage"])
        self.assertIsNone(p["day_extrema"])
    def test_wrong_issuer_fail(self):
        with self.assertRaises(ValueError):parse(source(SYMBOLS[0],DAYS[0]),SYMBOLS[1],DAYS[0])
    def test_original_and_gate(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/"one"
            v=run(dest,transport=lambda s,d:source(s,d,False))
            self.assertEqual(v["request_count"],4)
            self.assertEqual(v["full_days"],0)
            self.assertEqual(v["trade_gate"],"BLOCKED")
            self.assertEqual(len(list(dest.glob("*/source.bin"))),4)
            with self.assertRaises(ValueError):run(dest,transport=lambda s,d:b"")
if __name__=="__main__":unittest.main()
