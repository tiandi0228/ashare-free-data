"""In-memory source-side write boundary owner transitions are always fail closed."""
import json
import unittest
from pathlib import Path
from collector.p1_seven_boundary_ownership_transition_rehearsal import (
    rehearse,acceptance,
)

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/".github/workflows/p1-fresh-vendor-roster.yml").read_text()

class SevenWriterTransitionTests(unittest.TestCase):
    def test_full_transition_matrix(self):
        r=acceptance(SOURCE)
        self.assertEqual(r["tested_source_remote_write_boundaries"],7)
        self.assertEqual(r["transition_scenarios"],45)
        self.assertEqual(r["total_replayed_write_boundary_preflights"],315)
        self.assertTrue(r["all_after_transition_native_attempts_blocked"])
        self.assertFalse(r["production_write_path_integrated"])
        self.assertTrue(r["all_actual_remote_writes_zero"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_all_native_originals_research_only(self):
        r=rehearse(SOURCE)
        self.assertEqual(r["pretransition_native_research_eligible"],7)
        self.assertEqual(r["aftertransition_native_blocked"],0)
        self.assertEqual(r["actual_remote_writes"],0)
    def test_freeze_before_first_write(self):
        r=rehearse(SOURCE,transition_after=0)
        self.assertEqual(r["aftertransition_native_blocked"],7)
        self.assertTrue(all(x["reason"]=="CUTOVER_FREEZE_BLOCKS_ALL_P1_WRITES" for x in r["rows"]))
    def test_freeze_after_first_critical_roster_pin(self):
        r=rehearse(SOURCE,transition_after=1)
        self.assertEqual(r["pretransition_native_research_eligible"],1)
        self.assertEqual(r["aftertransition_native_blocked"],6)
        self.assertEqual(r["rows"][1]["remote_write_category"],"orphan_recovery_checkpoint")
    def test_freeze_after_first_three_writers(self):
        r=rehearse(SOURCE,transition_after=3)
        self.assertEqual(r["pretransition_native_research_eligible"],3)
        self.assertEqual(r["aftertransition_native_blocked"],4)
    def test_freeze_after_six_writers(self):
        r=rehearse(SOURCE,transition_after=6)
        self.assertEqual(r["aftertransition_native_blocked"],1)
        self.assertEqual(r["rows"][-1]["remote_write_category"],"pilot_receipt")
        self.assertEqual(r["rows"][-1]["reason"],"CUTOVER_FREEZE_BLOCKS_ALL_P1_WRITES")
    def test_external_only_block_every_old_native_at_start(self):
        r=rehearse(SOURCE,transition_after=0,mode="EXTERNAL_ONLY")
        self.assertEqual(r["aftertransition_native_blocked"],7)
        self.assertTrue(all(x["reason"]=="EXTERNAL_OWNER_NATIVE_SOURCE_VETO" for x in r["rows"]))
    def test_external_only_after_six_keeps_last_receipt_safe(self):
        r=rehearse(SOURCE,transition_after=6,mode="EXTERNAL_ONLY")
        self.assertEqual(r["aftertransition_native_blocked"],1)
        self.assertEqual(r["rows"][-1]["reason"],"EXTERNAL_OWNER_NATIVE_SOURCE_VETO")
    def test_contract_generation_replay_denied(self):
        r=rehearse(SOURCE,transition_after=2,attack="FORGED_OLD_GENERATION")
        self.assertEqual(r["aftertransition_native_blocked"],5)
        self.assertTrue(all(x["reason"]=="RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH" for x in r["rows"][2:]))
    def test_stale_sha_rejected(self):
        r=rehearse(SOURCE,transition_after=4,attack="STALE_RAW_SHA")
        self.assertEqual(r["aftertransition_native_blocked"],3)
        self.assertTrue(all(x["reason"]=="RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH" for x in r["rows"][4:]))
    def test_manual_trigger_still_blocked(self):
        r=rehearse(SOURCE,transition_after=3,attack="MANUAL_RUN")
        self.assertEqual(r["aftertransition_native_blocked"],4)
        self.assertEqual(r["rows"][-1]["reason"],"CUTOVER_FREEZE_BLOCKS_ALL_P1_WRITES")
    def test_late_created_run_still_blocked(self):
        r=rehearse(SOURCE,transition_after=5,attack="OLD_RUN_CREATED_AFTER_SWITCH")
        self.assertEqual(r["aftertransition_native_blocked"],2)
        self.assertEqual(r["rows"][-1]["reason"],"CUTOVER_FREEZE_BLOCKS_ALL_P1_WRITES")
    def test_invalid_transition_rejected(self):
        for transition in (-1,8,False,"3"):
            with self.subTest(transition=transition):
                with self.assertRaises(ValueError):
                    rehearse(SOURCE,transition_after=transition)
    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            rehearse(SOURCE,transition_after=0,mode="DUAL_ACTIVE")
    def test_no_policy_attacks_outside_transition(self):
        with self.assertRaises(ValueError):
            rehearse(SOURCE,attack="MANUAL_RUN")
    def test_mismatched_source_missing_writer_fails(self):
        source=SOURCE.replace("      - name: Archive raw CSV to durable free Git research branch",
                              "      - name: Untrusted modified archive")
        with self.assertRaises(ValueError):
            acceptance(source)
