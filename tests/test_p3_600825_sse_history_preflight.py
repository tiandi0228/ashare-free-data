import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from collector.p3_600825_sse_history_preflight import assess, assess_file

TICKS = "SecurityID,TickTime,Type,TickBSFlag,SendingTime\n"


class HistoricalCSVTests(unittest.TestCase):
    def test_no_input(self):
        self.assertEqual(assess(None, "l2-stock-tick")["status"], "NO_HISTORICAL_CSV_SUPPLIED")

    def test_scope_and_earliest(self):
        body = ("600825,2026090709145900,S,SUSP,20260907091459\n"
                "600826,2026090709000000,S,SUSP,20260907090000\n"
                "600825,2026090709145800,S,SUSP,20260907091458\n"
                "600825,2026090709000000,T,SUSP,20260907090000\n"
                "600825,2026090709000000,S,START,20260907090000\n")
        result = assess(StringIO(TICKS + body), "l2-stock-tick")
        self.assertEqual(result["security_rows"], 4)
        self.assertEqual(result["pre_auction_candidates"], 2)
        self.assertEqual(result["earliest_candidate_send_time_beijing"], "2026-09-07T09:14:58+08:00")
        for key in ("source_authenticated", "historical_snapshot_coverage_confirmed",
                    "official_first_release_verified", "initial_halt_before_auction_verified"):
            self.assertIs(result[key], False)
        self.assertEqual((result["trade_gate"], result["orders"]), ("BLOCKED", []))

    def test_tick_time_cannot_substitute_for_send_time(self):
        body = "".join(f"600825,2026090709145900,S,SUSP,{v}\n" for v in
                       ("20260907091500", "", "20260908090000", "20260907000000", "20260907093299"))
        result = assess(StringIO(TICKS + body), "l2-stock-tick")
        self.assertEqual(result["halt_at_or_after_auction"], 1)
        self.assertEqual(result["halt_send_clock_unusable"], 4)
        self.assertEqual(result["pre_auction_candidates"], 0)

    def test_snapshot_fields_are_not_interchangeable(self):
        for kind, field in (("l1-snapshot", "PhaseCode"), ("l2-snapshot", "TradingPhaseCode")):
            with self.subTest(kind=kind):
                body = (f"SecurityID,{field},SendingTime\n600825,P01     ,20260907091459\n"
                        "600825,S01     ,20260907091459\n600825,P11     ,20260907091459\n")
                self.assertEqual(assess(StringIO(body), kind)["pre_auction_candidates"], 1)
                with self.assertRaisesRegex(ValueError, "headers"):
                    assess(StringIO(body), "l2-stock-tick")

    def test_duplicate_headers_and_truncated_rows_rejected(self):
        for body in (TICKS.rstrip() + ",SendingTime\n", TICKS + "600825,,S,SUSP\n"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                assess(StringIO(body), "l2-stock-tick")

    def test_file_receipt_hashes_exact_bytes_and_locates_original_candidate(self):
        raw = ("\ufeff" + TICKS.rstrip() + ",TickIndex,ChannelNo\n"
               "600825,2026090709145900,S,SUSP,20260907091459,42,7\n"
               "600826,2026090709000000,S,SUSP,20260907090000,43,7\n").encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "StockTick.csv"
            path.write_bytes(raw)
            result = assess_file(path, "l2-stock-tick", expected_sha256=digest)
            self.assertEqual(result["input_sha256"], digest)
            candidate = result["earliest_candidate"]
            self.assertEqual((candidate["csv_record_end_line"], candidate["TickIndex"],
                              candidate["ChannelNo"]), (2, "42", "7"))
            self.assertFalse(result["source_authenticated"])
            path.write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                assess_file(path, "l2-stock-tick", expected_sha256=digest)

    def test_missing_candidate_is_not_proof(self):
        result = assess(StringIO(TICKS), "l2-stock-tick")
        self.assertIsNone(result["earliest_candidate"])
        self.assertFalse(result["initial_halt_before_auction_verified"])
