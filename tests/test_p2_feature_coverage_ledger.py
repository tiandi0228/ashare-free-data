"""Real original CSV fixture for retained cross-run research coverage receipts."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from collector.p2_feature_coverage_ledger import summarize

SHA="a"*64
END="2026-10-20"

def fixture(root):
    epoch=Path(root)/SHA[:16]
    epoch.mkdir(parents=True)
    (epoch/"archive_status.json").write_text(json.dumps({
        "source_sha256":SHA,"trade_gate":"BLOCKED"}))
    completed=[]
    receipts=[]
    for index,code,display in (
        (0,"sh.600000","600000"),
        (1,"sz.002249","002249")):
        folder=epoch/f"shard_{index:04d}"
        folder.mkdir()
        raw=("date,code,open,high,low,close,volume,amount,adjustflag,tradestatus\n"
             f"2026-10-20,{code},10,11,9,10,100,1000,3,1\n").encode()
        (folder/f"{code.replace('.','_')}.csv").write_bytes(raw)
        digest=hashlib.sha256(raw).hexdigest()
        original={"status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED",
                  "orders":[],"historical_point_in_time_universe_verified":False,
                  "issuer_count":1,
                  "results":[{"code":code,"sha256":digest,
                      "status":"OBSERVED_UNVERIFIED",
                      "rows":1,"tradable_rows":1,"suspended_status_rows":0}]}
        qraw=json.dumps(original).encode()
        (folder/"quality.json").write_bytes(qraw)
        completed.append({"index":index,"issuer_count":1,
                          "manifest_sha256":"b"*64,
                          "receipt_sha256":"c"*64})
        features=([{"issuer":code,"source_original_sha256":digest,
                    "asof_completed_day":END,"buy_signal":False}]
                  if index==0 else [])
        gaps=[] if index==0 else [{"issuer":code,"reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"}]
        receipts.append({
            "phase":"P2_PAGED_REAL_ARCHIVE_FEATURE_REPLAY",
            "status":"PAGED_REAL_ARCHIVE_RESEARCH_ONLY",
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "actionable_buy_signals":[],"historical_PIT_verified":False,
            "full_market_universe_verified":False,
            "source_epoch_sha256":SHA,
            "archive_commit_sha":"d"*40,
            "asof_completed_day":END,
            "selected_shards":[f"shard_{index:04d}"],
            "processed_shards":1,
            "scoped_verified_issuers":1,
            "computed_feature_issuers":len(features),
            "missing_feature_evidence_issuers":len(gaps),
            "features":features,"evidence_gaps":gaps})
    ledger={"phase":"P1_ROSTER_SHARD_LEDGER","source_sha256":SHA,
            "shard_count":4,"completed":completed,
            "completed_shards":2,"completed_issuers":2,
            "pending_shards":[2,3],"next_shard":2,
            "failed_in_this_reconciliation":[],
            "full_market_bars_certified":False,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
    return epoch,ledger,receipts

class CoverageTests(unittest.TestCase):
    def test_two_pages_one_gap_are_not_full_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            x=summarize(epoch,ledger,reports)
            self.assertEqual(x["status"],"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED")
            self.assertEqual(x["observed_archived_shards"],2)
            self.assertEqual(x["feature_complete_shards"],1)
            self.assertEqual(x["observed_with_feature_gaps_shards"],1)
            self.assertEqual(x["feature_issuer_count"],1)
            self.assertEqual(x["issuer_evidence_gap_count"],1)
            self.assertEqual(x["observed_feature_or_gap_issuers"],2)
            self.assertEqual(x["unobserved_issuer_count"],0)
            self.assertEqual(x["gap_reason_counts"],
                             {"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS":1})
            self.assertEqual(x["gap_issuer_codes"],["sz.002249"])
            self.assertEqual(x["gap_repair_queue"],[{
                "shard_id":"shard_0001",
                "issuer_gap_count":1,
                "issuer_reasons":[{"issuer":"sz.002249",
                                   "reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"}],
            }])
            self.assertTrue(x["gap_repair_queue_is_research_only"])
            self.assertTrue(x["full_archive_evidence_accounted"])
            self.assertFalse(x["full_archive_feature_coverage"])
            self.assertEqual(x["trade_gate"],"BLOCKED")
            self.assertEqual(x["orders"],[])
    def test_one_page_reports_unobserved_without_guessing(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            x=summarize(epoch,ledger,reports[:1])
            self.assertEqual(x["unobserved_shard_ids"],["shard_0001"])
            self.assertEqual(x["observed_archived_shards"],1)
            self.assertEqual(x["unobserved_issuer_count"],1)
            self.assertEqual(x["gap_repair_queue"],[])
            self.assertTrue(x["gap_repair_queue_is_research_only"])
            self.assertFalse(x["full_archive_evidence_accounted"])
    def test_duplicate_identical_shard_receipt_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            x=summarize(epoch,ledger,reports+[copy.deepcopy(reports[0])])
            self.assertEqual(x["observed_archived_shards"],2)
    def test_bad_checksum_and_original_csv_tamper_fail(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            reports[0]["features"][0]["source_original_sha256"]="e"*64
            self.assertEqual(summarize(epoch,ledger,reports)["status"],"REJECTED")
            epoch,ledger,reports=fixture_in_newdir(d)
            (epoch/"shard_0000"/"sh_600000.csv").write_text("tampered")
            self.assertEqual(summarize(epoch,ledger,reports)["status"],"REJECTED")
    def test_fake_safe_flags_or_forged_universe_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            reports[0]["trade_gate"]="OPEN"
            self.assertEqual(summarize(epoch,ledger,reports)["status"],"REJECTED")
            epoch,ledger,reports=fixture_in_newdir(d)
            reports[0]["full_market_universe_verified"]=True
            self.assertEqual(summarize(epoch,ledger,reports)["status"],"REJECTED")
    def test_missing_per_issuer_evidence_is_not_counted(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            reports[0]["features"].clear()
            reports[0]["computed_feature_issuers"]=0
            self.assertEqual(summarize(epoch,ledger,reports)["reason"],
                             "REPORT_0_MISSING_ISSUER_EVIDENCE")
    def test_wrong_epoch_and_forged_shard_fail(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            reports[0]["source_epoch_sha256"]="9"*64
            self.assertEqual(summarize(epoch,ledger,reports)["status"],"REJECTED")
            epoch,ledger,reports=fixture_in_newdir(d)
            reports[0]["selected_shards"]=["shard_9999"]
            self.assertEqual(summarize(epoch,ledger,reports)["status"],"REJECTED")
    def test_conflicting_gap_reason_on_same_immutable_csv_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            repeated=copy.deepcopy(reports[1])
            repeated["evidence_gaps"][0]["reason"]="MISSING_EXACT_ASOF_CLOSE"
            result=summarize(epoch,ledger,reports+[repeated])
            self.assertEqual(result["status"],"REJECTED")
            self.assertEqual(result["reason"],"CONFLICTING_REPEAT_GAP_REASON")

    def test_repair_queue_never_promotes_gap_to_buy_signal(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            x=summarize(epoch,ledger,reports)
            self.assertFalse(x["full_archive_feature_coverage"])
            self.assertFalse(x["coverage_certified_for_trading"])
            self.assertEqual(x["trade_gate"],"BLOCKED")
            self.assertEqual(x["orders"],[])
            self.assertEqual(x["executable_candidates"],[])
            self.assertEqual(x["actionable_buy_signals"],[])
            self.assertEqual(len(x["gap_repair_queue"]),1)

    def test_no_reports_is_explicit_no_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            x=summarize(epoch,ledger,[])
            self.assertEqual(x["unobserved_archived_shards"],2)
            self.assertEqual(x["feature_complete_shards"],0)
            self.assertFalse(x["full_archive_feature_coverage"])

def fixture_in_newdir(root):
    return fixture(Path(root)/"recreated")

if __name__=="__main__":unittest.main()
