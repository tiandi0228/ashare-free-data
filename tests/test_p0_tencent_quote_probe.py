"""Pure-offline Tencent public quote contract tests. Never call the provider."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from collector.p0_tencent_quote_probe import capture, parse, validate_symbols

A = "sh600519"
B = "sz002249"


def line(symbol, price="100.25", timestamp="20261106102959"):
    q = [""] * 39
    q[1] = "测试股票"
    q[2] = symbol[2:]
    q[3] = price
    q[4] = "99.50"
    q[30] = timestamp
    q[38] = "2.15"
    return ('v_' + symbol + '="' + '~'.join(q) + '";\n').encode("gb18030")


class TencentQuoteTests(unittest.TestCase):
    def test_bounded_main_board_only(self):
        self.assertEqual(validate_symbols([A, B]), [A, B])
        for symbols in ([], [A]*2, ["sh688001"], ["sz300015"],
                        ["sh600519;rm -rf /"], [A]*17):
            with self.subTest(symbols=symbols):
                with self.assertRaises(ValueError):
                    validate_symbols(symbols)

    def test_parse_two_names_independently(self):
        rows = parse(line(A) + line(B, "20.01"), [A, B])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["price"], 100.25)
        self.assertEqual(rows[1]["symbol"], B)
        self.assertEqual(rows[1]["state"], "NUMERIC_OBSERVED_UNVERIFIED")

    def test_missing_quote_not_filled(self):
        rows = parse(line(A), [A, B])
        self.assertEqual(rows[1]["state"], "MISSING_QUOTE")
        self.assertNotIn("price", rows[1])

    def test_zero_price_never_becomes_valid(self):
        rows = parse(line(A, "0"), [A])
        self.assertEqual(rows[0]["state"], "ZERO_PRICE_NEEDS_REVIEW")

    def test_rejects_corrupted_schema_and_timestamp(self):
        for raw in (line(A, timestamp="20261306102959"),
                    line(A).replace(b"600519", b"600518", 1),
                    line(A) + line(A)):
            with self.assertRaises(ValueError):
                parse(raw, [A])

    def test_embedded_or_trailing_unknown_provider_material_is_rejected(self):
        samples = (
            b"corrupt\\n" + line(A),
            line(A) + b"\\nunknown provider fragment",
            line(A) + b"garbage" + line(B),
            line(A) + b'v_sh600518="unexpected";',
        )
        for raw in samples:
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                parse(raw, [A, B])
        rows=parse(b"\\r\\n" + line(A) + b" \\n" + line(B) + b"\\n", [A,B])
        self.assertEqual(len(rows),2)

    def test_corrupted_response_preserved_for_forensic_replay(self):
        with tempfile.TemporaryDirectory() as root:
            raw=line(A) + b"unrecognized trailing garbage"
            dest=Path(root)/"broken"
            report=capture([A],dest,transport=lambda _: raw)
            self.assertEqual(report["status"],"FAILED_NO_TRADING")
            self.assertEqual((dest/"quote_response.bin").read_bytes(),raw)
            self.assertEqual(report["trade_gate"],"BLOCKED")
            self.assertEqual(report["orders"],[])

    def test_archives_original_bytes_and_blocks_trading(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root)/"probe"
            raw = line(A)
            report = capture([A], dest, transport=lambda _: raw,
                             now=datetime(2026,11,6,tzinfo=timezone.utc))
            self.assertEqual(report["status"], "OBSERVED_UNVERIFIED")
            self.assertEqual((dest/"quote_response.bin").read_bytes(), raw)
            self.assertFalse(report["historical_PIT_verified"])
            self.assertFalse(report["official_exchange_timestamp_verified"])
            self.assertEqual(report["trade_gate"], "BLOCKED")
            self.assertEqual(report["orders"], [])
            with self.assertRaises(ValueError):
                capture([A], dest, transport=lambda _: raw)

    def test_parse_failure_keeps_raw_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            dest=Path(root)/"broken"
            report=capture([A],dest,transport=lambda _: b"bad response")
            self.assertEqual(report["status"],"FAILED_NO_TRADING")
            self.assertEqual((dest/"quote_response.bin").read_bytes(), b"bad response")
            self.assertTrue((dest/"quality.json").exists())


if __name__ == "__main__":
    unittest.main()
