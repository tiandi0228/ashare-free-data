import json
import tempfile
import unittest
from pathlib import Path
from collector.eastmoney_daily_triangulation import parse, source_url, observe

def payload(symbol):
    market=1 if symbol.startswith("sh") else 0
    return json.dumps({"rc":0,"data":{"code":symbol[2:],"market":market,
      "klines":["2026-11-02,10,10.2,10.3,9.9,123",
                "2026-11-03,10.2,10.1,10.4,10,122"]}}).encode()

class TestThirdSource(unittest.TestCase):
    def test_bounded_unadjusted_parameter(self):
        for s in ("sh600519","sz002249"):
            self.assertIn("fqt=0",source_url(s))
        with self.assertRaises(ValueError):source_url("sz300015")

    def test_exact_two_dates_and_ohlc(self):
        q=parse(payload("sh600519"),"sh600519")
        self.assertEqual(len(q),2)
        self.assertEqual(q["2026-11-02"]["low"],"9.9")

    def test_mismatched_symbol_and_schema_fail(self):
        with self.assertRaises(ValueError):parse(payload("sh600519"),"sz002249")
        with self.assertRaises(ValueError):parse(b"invalid","sz002249")
        data=json.loads(payload("sz002249"))
        data["data"]["klines"]=["2026-11-02,10,10.2,9.8,9.9,0"]
        with self.assertRaises(ValueError):parse(json.dumps(data).encode(),"sz002249")

    def test_immutable_source_receipt_and_blocked_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"sample"
            x=observe(root,transport=payload)
            self.assertEqual(set(x),{"sh600519","sz002249"})
            for s in x:
                self.assertEqual((root/s/"source.bin").read_bytes(),payload(s))
                q=json.loads((root/s/"quality.json").read_text())
                self.assertEqual(q["trade_gate"],"BLOCKED")
                self.assertFalse(q["historical_PIT_verified"])
            with self.assertRaises(ValueError):observe(root,transport=payload)
if __name__=="__main__":unittest.main()
