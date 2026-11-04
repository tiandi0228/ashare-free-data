"""Backfill eligibility and original-source replay tests; no external GitHub calls."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.p2_historical_receipt_backfill import (
    eligible,import_report,recover,
)
from tests.test_p2_feature_coverage_ledger import fixture

def valid_run(rid=12345):
    return {"databaseId":rid,"status":"completed","conclusion":"success",
            "headBranch":"main","event":"push"}

class HistoricalReceiptBackfillTests(unittest.TestCase):
    def test_main_success_only(self):
        self.assertTrue(eligible(valid_run(),98765))
        for key,bad in (("event","pull_request"),("headBranch","feature/bad"),
                        ("status","in_progress"),("conclusion","failure"),
                        ("databaseId",0)):
            run=valid_run();run[key]=bad
            with self.subTest(key=key):self.assertFalse(eligible(run,98765))
        self.assertFalse(eligible(valid_run(),12345))
    def test_cross_epoch_legacy_and_tampered_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            r=reports[0]
            accepted,why=import_report(r,101,"a"*64,ledger,epoch,[])
            self.assertTrue(accepted)
            mismatched=copy.deepcopy(r)
            mismatched["source_epoch_sha256"]="f"*64
            self.assertEqual(import_report(mismatched,101,"a"*64,ledger,epoch,[])[1],
                             "DIFFERENT_FROZEN_EPOCH")
            legacy=copy.deepcopy(r);legacy["phase"]="P2_REAL_VENDOR_ARCHIVE_FEATURE_OBSERVATION"
            self.assertEqual(import_report(legacy,101,"a"*64,ledger,epoch,[])[1],
                             "LEGACY_ARTIFACT_NOT_PAGED")
            modified=copy.deepcopy(r)
            modified["features"][0]["source_original_sha256"]="0"*64
            self.assertEqual(import_report(modified,101,"a"*64,ledger,epoch,[])[1],
                             "ORIGINAL_RECEIPT_REPLAY_REJECTED")
    def test_bounded_recovery_cannot_treat_pr_as_success(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            path=Path(d)/"saved"
            record=valid_run(222)
            record_pr=valid_run(333);record_pr["event"]="pull_request"
            def fake_gh(args,timeout=45):
                class R: pass
                response=R();response.returncode=0
                if args[0:2]==["run","list"]:
                    response.stdout=json.dumps([record_pr,record])
                    return response
                self.assertEqual(args[0:2],["run","download"])
                self.assertEqual(args[2],"222")
                dest=Path(args[args.index("-D")+1])
                (dest/"p2_real_archive_feature_observation.json").write_text(
                    json.dumps(reports[0]))
                response.stdout=""
                return response
            with patch("collector.p2_historical_receipt_backfill.gh",
                       side_effect=fake_gh):
                out=recover("tiandi0228/ashare-free-data","a"*64,
                            epoch,ledger,path,99999)
            self.assertEqual(out["imported_run_ids"],[222])
            self.assertEqual(out["inspected_runs"],1)
            self.assertEqual(out["observed_archived_shards_after_import"],1)
            self.assertTrue((path/"222.json").exists())
            self.assertFalse((path/"333.json").exists())
            self.assertEqual(out["trade_gate"],"BLOCKED")
    def test_expired_or_missing_artifacts_not_counted(self):
        with tempfile.TemporaryDirectory() as d:
            epoch,ledger,reports=fixture(d)
            path=Path(d)/"saved"
            def fake_gh(args,timeout=45):
                class R: pass
                result=R()
                if args[:2]==["run","list"]:
                    result.returncode=0
                    result.stdout=json.dumps([valid_run(123)])
                else:
                    result.returncode=1;result.stdout=""
                return result
            with patch("collector.p2_historical_receipt_backfill.gh",
                       side_effect=fake_gh):
                out=recover("tiandi0228/ashare-free-data","a"*64,
                            epoch,ledger,path,99999)
            self.assertEqual(out["imported_run_ids"],[])
            self.assertEqual(out["observed_archived_shards_after_import"],0)
            self.assertEqual(out["skipped_runs"][0]["reason"],
                             "ARTIFACT_UNAVAILABLE_OR_EXPIRED")
if __name__=="__main__":unittest.main()
