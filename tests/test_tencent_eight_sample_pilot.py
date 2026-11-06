"""Entirely offline tests for finite Tencent live research plan."""
import json
import tempfile
import unittest
from pathlib import Path
from collector.tencent_eight_sample_pilot import collect, plan, MAX_REQUESTS
from collector import p1_tencent_minute_probe as minute


def quote_payload(symbols):
    pieces = []
    for symbol in symbols:
        fields = [""] * 39
        fields[1] = "测试"
        fields[2] = symbol[2:]
        fields[3], fields[4], fields[30] = "10.1", "10", "20261106102959"
        pieces.append('v_'+symbol+'="'+'~'.join(fields)+'";')
    return ("\n".join(pieces)).encode("gb18030")


def minute_payload(symbol, period):
    return json.dumps({"code":0,"data":{symbol:{period:[
        ["202611060935","10","10.1","10.2","9.9","100"],
        ["202611060940","10.1","10.2","10.3","10","75"],
    ]}}}).encode()


class TencentSampleTests(unittest.TestCase):
    def test_fixed_budget_and_mainboard(self):
        tasks = plan()
        self.assertEqual(len(tasks), MAX_REQUESTS)
        self.assertEqual(tasks[0][0], "quote")
        self.assertEqual(len(tasks[0][1]), 8)
        self.assertEqual(len([x for x in tasks if x[0] == "minute"]), 10)

    def test_all_eleven_offline_observations_are_research_only(self):
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/"capture"
            report=collect(
                dest,
                quote_transport=lambda symbols: quote_payload(symbols),
                minute_transport=lambda symbol, period: minute_payload(symbol,period)
            )
            self.assertEqual(report["successful_request_count"],11)
            self.assertEqual(report["quote_numeric_observed_count"],8)
            self.assertEqual(report["request_count"],11)
            self.assertFalse(report["full_market_bars_certified"])
            self.assertFalse(report["historical_PIT_verified"])
            self.assertFalse(report["real_time_freshness_certified"])
            self.assertEqual(report["trade_gate"],"BLOCKED")
            self.assertEqual(report["orders"],[])
            self.assertTrue((dest/"summary.json").exists())
            self.assertEqual(len(list(dest.glob("*/quality.json"))),11)
            with self.assertRaises(ValueError):
                collect(dest,quote_transport=lambda _:b"",minute_transport=lambda *_:b"")

    def test_one_source_failure_does_not_hide_remaining_samples(self):
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/"capture"
            report=collect(
                dest,
                quote_transport=lambda symbols: quote_payload(symbols),
                minute_transport=lambda symbol, period: b"blocked" if period=="m1" else minute_payload(symbol,period)
            )
            self.assertEqual(report["successful_request_count"],9)
            self.assertEqual(report["status"],"PARTIAL_OR_FAILED_UNVERIFIED")
            self.assertEqual(len(report["results"]),11)
            self.assertEqual(len(list(dest.glob("*/quality.json"))),11)
            self.assertFalse(report["all_minute_periods_observed"])
            self.assertEqual(report["trade_gate"],"BLOCKED")


if __name__ == "__main__":
    unittest.main()
