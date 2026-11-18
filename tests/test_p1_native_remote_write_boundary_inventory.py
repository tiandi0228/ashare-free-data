"""Source-side P1 remote write boundary inventory: fail closed on any escape."""
import unittest
from pathlib import Path
from collector.p1_native_remote_write_boundary_inventory import audit,render_preview,REQUIRED

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/".github/workflows/p1-fresh-vendor-roster.yml").read_text()

class WriteBoundaryTests(unittest.TestCase):
    def test_seven_actual_main_source_remote_mutations_identified(self):
        out=audit(SOURCE)
        self.assertEqual(out["known_remote_writer_count"],7)
        self.assertEqual({x["step_name"] for x in out["source_remote_writers"]},set(REQUIRED))
        self.assertTrue(out["source_serial_concurrency_confirmed"])
        self.assertFalse(out["production_gate_deployed"])
        self.assertEqual(out["trade_gate"],"BLOCKED")
    def test_nonexecutable_preview_has_one_gate_per_remote_writer(self):
        a=render_preview(SOURCE)
        self.assertEqual(a["reviewed_boundaries"],7)
        self.assertTrue(a["staged_gate_is_deliberately_unconditional_block"])
        self.assertTrue(a["preview_text"].startswith("DO NOT DEPLOY OR MERGE AS WORKFLOW"))
        self.assertEqual(a["preview_text"].count("echo \"BLOCKED: immutable live owner"),7)
        self.assertEqual(a["preview_text"].count("exit 77"),7)
        self.assertFalse(a["source_gate_installed"])
    def test_existing_live_source_not_proven_gated(self):
        with self.assertRaisesRegex(ValueError,"missing per-boundary ownership"):
            audit(SOURCE,require_gate=True)
    def test_preview_body_is_covered_in_strict_check(self):
        preview=render_preview(SOURCE)
        body=preview["preview_text"].split("\n",1)[1]
        self.assertEqual(audit(body,require_gate=True)["known_remote_writer_count"],7)
    def test_remove_roster_pin_rejected(self):
        corrupt=SOURCE.replace(
          "      - name: Pin authenticated-by-SHA vendor bytes for repeatable P1 research",
          "      - name: Misc pin operation")
        with self.assertRaises(ValueError):audit(corrupt)
    def test_remove_conditional_orphan_recovery_writer_rejected(self):
        corrupt=SOURCE.replace("python -m collector.p1_checkpoint --mode write \\",
                               "python -m collector.p1_checkpoint --mode read \\")
        with self.assertRaises(ValueError):audit(corrupt)
    def test_missing_primary_raw_csv_archive_rejected(self):
        corrupt=SOURCE.replace("python -m collector.p1_csv_archive --plan ",
                               "python -m collector.p1_dummy --plan ")
        with self.assertRaises(ValueError):audit(corrupt)
    def test_missing_normal_checkpoint_write_rejected(self):
        corrupt=SOURCE.replace(
          "run: python -m collector.p1_checkpoint --mode write",
          "run: python -m collector.p1_checkpoint --mode read")
        with self.assertRaises(ValueError):audit(corrupt)
    def test_missing_gap_repair_archive_rejected(self):
        corrupt=SOURCE.replace("          archive(plan,[(int(",
                               "          skip_archive(plan,[(int(")
        with self.assertRaises(ValueError):audit(corrupt)
    def test_missing_scheduled_receipt_writer_rejected(self):
        corrupt=SOURCE.replace(
          "python -m collector.p1_schedule_run_provenance \\",
          "python -m collector.p1_schedule_run_dryrun \\")
        with self.assertRaises(ValueError):audit(corrupt)
    def test_missing_pilot_receipt_writer_rejected(self):
        corrupt=SOURCE.replace(
          "python -m collector.p1_dual_pilot_receipt \\",
          "python -m collector.p1_dual_pilot_dryrun \\")
        with self.assertRaises(ValueError):audit(corrupt)
    def test_duplicate_write_step_name_rejected(self):
        token="      - name: Archive raw CSV to durable free Git research branch"
        with self.assertRaises(ValueError):audit(SOURCE+"\n"+token+"\n")
    def test_unrecognized_new_csv_writer_rejected(self):
        needle="      - name: Publish P1 run diagnostics (research only)"
        extra=("      - name: Unexpected external CSV persistence\n"
               "        run: python -m collector.p1_csv_archive --plan evidence/shards/plan.json\n")
        self.assertIn(needle,SOURCE)
        with self.assertRaisesRegex(ValueError,"unreviewed new remote mutation"):
            audit(SOURCE.replace(needle,extra+needle))
    def test_no_serial_concurrency_rejected(self):
        with self.assertRaisesRegex(ValueError,"serial schedule"):
            audit(SOURCE.replace("cancel-in-progress: false","cancel-in-progress: true"))
    def test_preview_guard_removed_from_one_boundary_rejected(self):
        body=render_preview(SOURCE)["preview_text"].split("\n",1)[1]
        removed=body.replace(
          "      - name: OWNERSHIP FENCE BEFORE Archive raw CSV to durable free Git research branch",
          "      - name: Deleted guard archive")
        with self.assertRaisesRegex(ValueError,"missing per-boundary ownership"):
            audit(removed,require_gate=True)
    def test_report_never_promotes_trade_or_production(self):
        result=audit(SOURCE)
        self.assertFalse(result["production_cutover_authorized"])
        self.assertFalse(result["external_dispatch_authorized"])
        self.assertEqual(result["orders"],[])
        self.assertEqual(result["executable_candidates"],[])
