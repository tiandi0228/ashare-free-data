import base64
import io
import unittest

from collector.p3_sina_preauction_probe import build_result, capture


def frame(symbol="sh600825", date="2026-11-16", time="09:14:57", status="03"):
    values = ["证券"] + ["0"] * 29 + [date, time] + ([] if status is None else [status])
    return (f'var hq_str_{symbol}="' + ",".join(values) + '";\n').encode("gb18030")


class ProbeTests(unittest.TestCase):
    at = "2026-11-16T09:14:58+08:00"

    def test_no_inferred_halt_and_exact_bytes(self):
        raw = frame()
        result = build_result(raw, "sh.600825", self.at)
        self.assertEqual(base64.b64decode(result["raw_base64"]), raw)
        self.assertEqual(result["provider_status_raw"], "03")
        self.assertEqual(result["normalized_status_claim"], "UNKNOWN")
        self.assertEqual(result["timing"], "SAME_DAY_CAPTURE_BEFORE_0915")
        self.assertFalse(result["preauction_visibility_certified"])
        self.assertEqual(result["trade_gate"], "BLOCKED")

    def test_sse_optional_trailing_empty_field(self):
        raw = frame().replace(b'";', b',";')
        result = build_result(raw, "sh.600825", self.at)
        self.assertEqual(result["provider_status_raw"], "03")
        self.assertEqual(base64.b64decode(result["raw_base64"]), raw)

    def test_late_stale_and_missing(self):
        self.assertEqual(build_result(frame(), "sh.600825", "2026-11-16T09:15:00+08:00")["timing"],
                         "NOT_CAPTURED_BEFORE_0915")
        self.assertEqual(build_result(frame(date="2026-11-13"), "sh.600825", self.at)["timing"],
                         "SOURCE_NOT_CAPTURE_DAY")
        result = build_result(frame(date="", time="", status=None), "sh.600825", self.at)
        self.assertEqual(result["timing"], "NO_SOURCE_CLOCK")
        self.assertIsNone(result["provider_status_raw"])

    def test_bad_payloads(self):
        for raw in (b"<html></html>", frame(symbol="sh600000"), frame(time="99:99:99"),
                    frame(time="09:15:01"), b'var hq_str_sh600825="";'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                build_result(raw, "sh.600825", self.at)

    def test_one_request_and_local_clock(self):
        class Response(io.BytesIO):
            status = 200

        class Opener:
            calls = []

            def open(self, request, timeout):
                self.calls.append((request.full_url, request.get_header("Referer"), timeout))
                return Response(frame(date="2020-01-02"))

        opener = Opener()
        result = capture("sh.600825", opener=opener)
        self.assertEqual(opener.calls, [("https://hq.sinajs.cn/list=sh600825", "https://finance.sina.com.cn/", 8)])
        self.assertEqual(result["timing"], "SOURCE_NOT_CAPTURE_DAY")
        self.assertFalse(result["capture_clock_attested"])
