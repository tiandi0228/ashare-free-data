"""Offline checks only; no Tencent network calls."""
import json
import tempfile
import unittest
from pathlib import Path

from collector.p1_tencent_minute_probe import parse, capture, request_url, LIMIT_BYTES


def payload(rows=None, symbol="sz002249", period="m5"):
    if rows is None:
        rows=[["202611060935", "10", "10.2", "10.3", "9.9", "100"],
              ["202611060940", "10.2", "10.1", "10.4", "10.0", "80"]]
    return json.dumps({"code":0,"data":{symbol:{period:rows}}}).encode()


class TencentMinuteTests(unittest.TestCase):
    def test_five_periods_have_bounded_url(self):
        for p in ("m1","m5","m15","m30","m60"):
            self.assertIn(f"sz002249,{p},,240",request_url("sz002249",p))
        for sym,period in (("sz300015","m5"),("sh688001","m5"),
                           ("sz002249","m2")):
            with self.assertRaises(ValueError):
                request_url(sym,period)

    def test_valid_ordered_bars_with_vendor_native_volume(self):
        result=parse(payload(),"sz002249","m5")
        self.assertEqual(result[0]["volume_provider_units"],100)
        self.assertEqual(result[-1]["close"],10.1)
        self.assertNotIn("volume_shares",result[0])

    def test_inconsistent_ohlc_fails(self):
        for bad in (["202611060935","10","10.2","9.8","9.9","100"],
                    ["202611060935","10","10.2","10.3","9.9","-1"],
                    ["202611060935","0","0","0","0","0"]):
            with self.assertRaises(ValueError):
                parse(payload([bad]),"sz002249","m5")

    def test_out_of_order_duplicate_and_out_of_session(self):
        cases=[
            [["202611060940",10,10,10,10,10],["202611060935",10,10,10,10,10]],
            [["202611060935",10,10,10,10,10]]*2,
            [["202611061210",10,10,10,10,10]],
            [["202613060935",10,10,10,10,10]],
        ]
        for rows in cases:
            with self.subTest(rows=rows),self.assertRaises(ValueError):
                parse(payload(rows),"sz002249","m5")

    def test_wrong_symbol_or_period_is_rejected(self):
        for raw in (payload(symbol="sh600519"),payload(period="m1"),
                    b"not-json",json.dumps({"code":1,"data":{}}).encode()):
            with self.assertRaises(ValueError):
                parse(raw,"sz002249","m5")

    def test_immutable_evidence_and_blocked_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"sample"
            raw=payload()
            q=capture("sz002249","m5",dest,transport=lambda *_: raw)
            self.assertEqual(q["status"],"OBSERVED_UNVERIFIED")
            self.assertEqual((dest/"response.bin").read_bytes(),raw)
            self.assertEqual(len(json.loads((dest/"bars.json").read_text())),2)
            self.assertFalse(q["bars_certified"])
            self.assertFalse(q["historical_PIT_verified"])
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertEqual(q["orders"],[])
            with self.assertRaises(ValueError):
                capture("sz002249","m5",dest,transport=lambda *_:raw)

    def test_failure_retains_bad_raw_with_no_bars(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"failed"
            q=capture("sz002249","m1",dest,transport=lambda *_:b"broken")
            self.assertEqual(q["status"],"FAILED_UNVERIFIED")
            self.assertTrue((dest/"response.bin").exists())
            self.assertFalse((dest/"bars.json").exists())

    def test_reject_oversized_payload(self):
        with self.assertRaises(ValueError):
            parse(b"x"*(LIMIT_BYTES+1),"sz002249","m1")


if __name__=="__main__":
    unittest.main()
