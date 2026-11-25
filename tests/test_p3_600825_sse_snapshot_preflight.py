import unittest

from collector.p3_600825_sse_snapshot_preflight import SPEC, assess


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        # Synthetic excerpt only. It is not a September 7 market record.
        self.row = dict(schema=SPEC, venue="SSE", MsgType="M102", SecurityType=1,
                        TradSesMode=3, TradeDate="20260907", MDStreamID="MD002",
                        SecurityID="600825", TradingPhaseCode="P01     ",
                        SendingTime="20260907091459999", LastUpdateTime="091459000")

    def test_no_snapshot(self):
        report = assess()
        self.assertEqual(report["status"], "NO_HISTORICAL_SNAPSHOT_SUPPLIED")
        self.assertFalse(report["historical_snapshot_coverage_confirmed"])

    def test_candidate_cannot_promote_provenance(self):
        report = assess(dict(self.row, source_authenticated=True,
                             official_first_release_verified=True, trade_gate="OPEN"))
        self.assertEqual(report["status"], "PRE_AUCTION_HALT_CANDIDATE_PROVENANCE_REQUIRED")
        for key in ("source_authenticated", "initial_halt_before_auction_verified",
                    "official_first_release_verified", "historical_PIT_verified"):
            self.assertIs(report[key], False)
        self.assertEqual((report["trade_gate"], report["orders"]), ("BLOCKED", []))

    def test_exchange_send_time_controls_cutoff(self):
        report = assess(dict(self.row, SendingTime="20260907091500000"))
        self.assertEqual(report["status"], "HALT_SENT_AT_OR_AFTER_AUCTION")

    def test_startup_and_non_trade_flags_do_not_mean_halt(self):
        for phase in ("S01     ", "N01     ", "S010    "):
            with self.subTest(phase=phase):
                self.assertEqual(assess(dict(self.row, TradingPhaseCode=phase))["status"],
                                 "NO_EXPLICIT_HALT_IN_THIS_ROW")

    def test_different_stream_security_or_test_mode_rejected(self):
        for values in (dict(MsgType="M101"), dict(MDStreamID="MD001"),
                       dict(SecurityID="600826"), dict(TradSesMode=1),
                       dict(SecurityType=True), dict(TradeDate="20260908"), dict(schema="0.63")):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "pinned"):
                assess(dict(self.row, **values))

    def test_malformed_or_conflicting_fields_rejected(self):
        for values in (dict(TradingPhaseCode="P11     "), dict(TradingPhaseCode="P01"),
                       dict(LastUpdateTime="091500000"), dict(LastUpdateTime="000000000"),
                       dict(LastUpdateTime=91459000), dict(SendingTime="20260908091459999"),
                       dict(SendingTime="20260907096159999")):
            with self.subTest(values=values), self.assertRaises(ValueError):
                assess(dict(self.row, **values))
