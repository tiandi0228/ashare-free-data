"""Source-bound paging tests: immutable checksum, no silent truncation, no trades."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collector.p2_paged_real_archive import run

SHA="a"*64
COMMIT="b"*40

def setup(tmp,n):
    root=Path(tmp)
    archive=root/"archive"
    epoch=archive/SHA[:16]
    epoch.mkdir(parents=True)
    (epoch/"archive_status.json").write_text(json.dumps({
        "source_sha256":SHA,"trade_gate":"BLOCKED"}))
    checkpoint=root/"checkpoints"
    checkpoint.mkdir()
    completed=[]
    for i in range(n):
        sub=epoch/f"shard_{i:04d}"
        sub.mkdir()
        (sub/"quality.json").write_text("{}")
        completed.append({"index":i,"issuer_count":8,
                          "manifest_sha256":"c"*64,"receipt_sha256":"d"*64})
    ledger={"phase":"P1_ROSTER_SHARD_LEDGER",
            "source_sha256":SHA,"shard_count":40,
            "completed":completed,"completed_shards":n,
            "completed_issuers":n*8,
            "pending_shards":list(range(n,40)),
            "next_shard":n if n<40 else None,
            "failed_in_this_reconciliation":[],
            "full_market_bars_certified":False,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    (checkpoint/(SHA+".json")).write_text(json.dumps(ledger))
    return archive,checkpoint,root/"evidence/report.json"

def pretend_success(stage,asof,max_issuers):
    shards=list(Path(stage).glob("*/shard_*/quality.json"))
    assert 1<=len(shards)<=16
    return {"status":"REAL_ARCHIVED_BAR_FEATURES_RESEARCH_ONLY",
            "trade_gate":"BLOCKED","orders":[],"actionable_buy_signals":[],
            "historical_PIT_verified":False,"full_market_universe_verified":False,
            "scoped_verified_issuers":len(shards)*8,
            "feature_issuers":len(shards)*8,
            "insufficient_evidence_issuers":0,
            "features":[],"evidence_gaps":[]}

class PagedArchiveTests(unittest.TestCase):
    def test_rotation_covers_multiple_pages_without_claiming_market(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,c,o=setup(tmp,33)
            with patch("collector.p2_paged_real_archive.subprocess.check_output",
                       return_value=COMMIT+"\n"),patch(
                "collector.p2_paged_real_archive.observe",side_effect=pretend_success):
                first=run(a,c,o,run_number=1)
                middle=run(a,c,o,run_number=2)
                last=run(a,c,o,run_number=3)
                rotated=run(a,c,o,run_number=4)
            self.assertEqual([v["page_index"] for v in
                              (first,middle,last,rotated)],[0,1,2,0])
            self.assertEqual([v["processed_shards"] for v in
                              (first,middle,last)],[16,16,1])
            self.assertEqual(len(set(first["selected_shards"])|
                                 set(middle["selected_shards"])|
                                 set(last["selected_shards"])),33)
            self.assertEqual(first["archived_shards_in_selected_epoch"],33)
            self.assertEqual(first["checkpoint_completed_shards"],33)
            self.assertEqual(first["trade_gate"],"BLOCKED")
            self.assertEqual(first["orders"],[])
            self.assertFalse(first["full_market_universe_verified"])
    def test_manual_page_and_out_of_range_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,c,o=setup(tmp,17)
            with patch("collector.p2_paged_real_archive.subprocess.check_output",
                       return_value=COMMIT+"\n"),patch(
                "collector.p2_paged_real_archive.observe",side_effect=pretend_success):
                r=run(a,c,o,page=1,run_number=1)
                bad=run(a,c,o,page=2)
            self.assertEqual(r["processed_shards"],1)
            self.assertEqual(r["selection_method"],"EXPLICIT_PAGE")
            self.assertEqual(bad["reason"],"PAGE_OUT_OF_RANGE")
            self.assertNotIn("features",bad)
    def test_unarchived_fake_ledger_shards_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,c,o=setup(tmp,1)
            sub=a/SHA[:16]/"shard_0000"
            sub.rename(a/SHA[:16]/"shard_0039")
            with patch("collector.p2_paged_real_archive.subprocess.check_output",
                       return_value=COMMIT+"\n"):
                r=run(a,c,o)
            self.assertEqual(r["reason"],
                             "ARCHIVED_SHARD_ABSENT_FROM_FROZEN_LEDGER")
            self.assertEqual(r["orders"],[])
    def test_bad_checkpoint_is_not_a_certified_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,c,o=setup(tmp,1)
            f=c/(SHA+".json")
            data=json.loads(f.read_text())
            data["trade_gate"]="OPEN"
            f.write_text(json.dumps(data))
            with patch("collector.p2_paged_real_archive.subprocess.check_output",
                       return_value=COMMIT+"\n"):
                r=run(a,c,o)
            self.assertEqual(r["status"],"REJECTED")
            self.assertFalse(r["historical_PIT_verified"])
    def test_unverified_indicator_result_blocks_entire_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,c,o=setup(tmp,1)
            def unsafe(*args,**kwargs):
                result=pretend_success(*args,**kwargs)
                result["orders"]=[{"side":"BUY"}]
                return result
            with patch("collector.p2_paged_real_archive.subprocess.check_output",
                       return_value=COMMIT+"\n"),patch(
                "collector.p2_paged_real_archive.observe",side_effect=unsafe):
                r=run(a,c,o)
            self.assertEqual(r["reason"],"PAGED_ORIGINAL_REPLAY_REJECTED")
            self.assertEqual(r["orders"],[])
    def test_invalid_run_number_does_not_open_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,c,o=setup(tmp,1)
            r=run(a,c,o,run_number=0)
            self.assertEqual(r["reason"],"INVALID_RUN_NUMBER")
            self.assertEqual(r["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
