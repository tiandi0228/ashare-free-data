import json
import tempfile
import unittest
from pathlib import Path
from collector.tencent_daily_extrema_triangulation import parse,capture,source_url
def source(symbol):
    return json.dumps({"code":0,"data":{symbol:{
      "day":[["2026-11-02","100","102","103","99","800"],
             ["2026-11-03","102","103","104","101","900"]],
      "qfqday":[["2026-11-02","1","2","3","1","900"]]}}}).encode()
class TestDaily(unittest.TestCase):
    def test_two_symbol_budget(self):
        self.assertIn("sh600519,day",source_url("sh600519"))
        for value in ("sz300015","sh688001","sh601318"):
            with self.assertRaises(ValueError):source_url(value)
    def test_unadjusted_only(self):
        self.assertEqual(parse(source("sz002249"),"sz002249")["2026-11-02"]["low"],"99")
        p={"code":0,"data":{"sz002249":{"qfqday":[["2026-11-02",1,2,3,1,2]]}}}
        with self.assertRaises(ValueError):parse(json.dumps(p).encode(),"sz002249")
    def test_invalid_ohlc_and_date(self):
        for rows in (
             [["2026-11-02","100","102","101","99","8"]],
             [["2026-11-03","100","102","103","99","8"],["2026-11-02","100","102","103","99","8"]]):
            p={"code":0,"data":{"sz002249":{"day":rows}}}
            with self.assertRaises(ValueError):parse(json.dumps(p).encode(),"sz002249")
    def test_immutable_original_and_trading_block(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"evidence"
            data=capture(dest,transport=source)
            self.assertEqual(set(data),{"sh600519","sz002249"})
            self.assertEqual(len(data["sh600519"]),2)
            self.assertEqual((dest/"sz002249"/"raw.bin").read_bytes(),source("sz002249"))
            q=json.loads((dest/"sh600519"/"quality.json").read_text())
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertFalse(q["historical_PIT_verified"])
            with self.assertRaises(ValueError):capture(dest,transport=source)
if __name__=="__main__": unittest.main()
