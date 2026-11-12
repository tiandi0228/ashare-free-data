"""Current P2 SHA replay must retain exact gap identities across P3 research."""
import copy
import unittest
from pathlib import Path
import json
from collector.p2_p3_live_gap_reference_queue import join
from collector.p3_three_issuer_halt_source_crosswalk import SHAS
from collector.p3_four_issuer_st_crosswalk import EXPECTED
from collector.p2_original_gap_action_triage import EPOCH

ROOT=Path(__file__).resolve().parents[1]
MISSING={
 "sh.601238":("shard_0104","a2f6d4f36ec5487329a8e66a56bdf872c4dfc1e9a1cb2eb565994628800b7e65",10),
 "sh.601995":("shard_0120","c62152568423890c5bfc384fa4e0ec34e9ef71b9a092011b75b83a9e282d6609",6),
 "sh.603183":("shard_0140","3f53cf0bd447c2d757488614b4236632069885e793ee04959ae0c888c614168c",2),
 "sh.603517":("shard_0166","f6e5848ea8ff0e682608d96342adf68594140f9e7eac3aaad75afbfb2dc2394a",1),
 "sh.603759":("shard_0182","b5d17da3ca737e21479b5e4b5a1ad41c7f13f777f42b8eaf419f30c35dcce4dc",1),
 "sh.603838":("shard_0186","98441e8dcbfae442ec14a7004a95ce5abff8d876b8cd69e1e754a77b16436e86",1),
 "sz.002860":("shard_0378","c1e9e5844abed70f2471cb337bf917f584f0029109aac7c0bfb80ae85ad1d188",10),
 "sz.002870":("shard_0379","9f69a30a532df4e4178109d0c886f30c82e1f8fd1cf9e0fb3693f13582d3935a",1),
}
def sample():
    known={**{k:v for k,v in SHAS.items()},
           **{k:(v[0],v[1],v[2]) for k,v in EXPECTED.items()},**MISSING}
    queue={}
    for code,(shard,sha,count) in known.items():
        queue.setdefault(shard,[]).append({
          "issuer":code,"reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS",
          "original_gap_diagnostic":{
            "category":"VENDOR_SUSPENDED_IN_LAST_21_ROWS",
            "vendor_rows_at_or_before_asof":485,
            "last_21_vendor_rows_suspended":count,
            "first_vendor_row_day":"2024-10-21",
            "last_vendor_row_day":"2026-10-20",
            "exact_asof_vendor_row_present":True,
            "original_csv_sha256":sha,
            "vendor_calendar_independently_verified":False,
            "historical_PIT_verified":False,
            "repair_approved":False
          }})
    queue["shard_0097"]=[{
      "issuer":"sh.601091","reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS",
      "original_gap_diagnostic":{
        "category":"FEWER_THAN_21_VENDOR_ROWS_ASOF",
        "vendor_rows_at_or_before_asof":18,
        "last_21_vendor_rows_suspended":0,
        "first_vendor_row_day":"2026-09-17",
        "last_vendor_row_day":"2026-10-20",
        "exact_asof_vendor_row_present":True,
        "original_csv_sha256":"a99a8383f8a3a41682a7264cac5a1a3097831bb2e456c2c36d09c188b8fcdf3d",
        "vendor_calendar_independently_verified":False,
        "historical_PIT_verified":False,"repair_approved":False
      }}]
    assert sum(map(len,queue.values()))==16 and len(queue)==15
    summary={
      "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
      "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
      "source_epoch_sha256":EPOCH,
      "checkpoint_completed_shards":242,
      "archived_original_shards":242,
      "observed_archived_shards":242,
      "feature_complete_shards":227,
      "observed_with_feature_gaps_shards":15,
      "unobserved_archived_shards":0,
      "issuer_evidence_gap_count":16,
      "gap_reason_counts":{"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS":16},
      "gap_repair_queue":[{"shard_id":shard,"issuer_gap_count":len(items),
                           "issuer_reasons":items} for shard,items in sorted(queue.items())],
      "gap_shard_ids":sorted(queue),
      "gap_repair_queue_is_research_only":True,
      "trade_gate":"BLOCKED",
      "historical_PIT_verified":False,
      "coverage_certified_for_trading":False,
      "orders":[],"executable_candidates":[],
    }
    three=json.loads((ROOT/"evidence/p3_issuer_halt_resume_three_research_refs.json").read_text())
    four=json.loads((ROOT/"evidence/p3_four_issuer_halt_st_research_refs.json").read_text())
    return [summary,copy.deepcopy(summary),three,four]

class LiveP2P3GapQueue(unittest.TestCase):
    def setUp(self):self.args=sample()
    def check(self):return join(*self.args)
    def reject(self):
        with self.assertRaises(ValueError):self.check()
    def test_live_242_gap_queue_all_original_ids_preserved(self):
        r=self.check()
        self.assertEqual(r["current_same_epoch_original_shards"],242)
        self.assertEqual(r["current_replayed_feature_complete_shards"],227)
        self.assertEqual(r["curated_p3_reference_issuer_count"],7)
        self.assertEqual(r["missing_p3_halt_source_reference_issuer_count"],8)
        self.assertEqual({x["issuer"] for x in r["missing_official_halt_source_research_queue"]},set(MISSING))
        self.assertEqual(r["short_ipo_history_research_queue"][0]["issuer"],"sh.601091")
        self.assertFalse(r["issuer_pdf_bytes_sha_verified"])
        self.assertEqual(r["feature_shards_promoted"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_unchanged_241_historical_is_not_current(self):
        self.args[0]["checkpoint_completed_shards"]=241
        self.reject()
    def test_live_report_must_match_independently_replayed_report(self):
        self.args[1]["gap_shard_ids"].pop()
        self.reject()
    def test_wrong_gap_original_csv_sha_rejected(self):
        self.args[0]["gap_repair_queue"][0]["issuer_reasons"][0]["original_gap_diagnostic"]["original_csv_sha256"]="f"*64
        self.args[1]=copy.deepcopy(self.args[0])
        self.reject()
    def test_wrong_existing_p3_pdf_url_rejected(self):
        self.args[2]["pairs"][0]["docs"][0]["url"]="https://example.invalid/fake.pdf"
        self.reject()
    def test_wrong_historical_st_source_rejected(self):
        self.args[3]["cases"][0]["st_start"]="2026-10-01"
        self.reject()
    def test_forged_official_pit_promotion_rejected(self):
        self.args[0]["historical_PIT_verified"]=True
        self.reject()
    def test_duplicate_issuer_in_current_gap_queue_rejected(self):
        self.args[0]["gap_repair_queue"][1]["issuer_reasons"][0]["issuer"]=self.args[0]["gap_repair_queue"][0]["issuer_reasons"][0]["issuer"]
        self.args[1]=copy.deepcopy(self.args[0])
        self.reject()
    def test_observed_shards_cannot_claim_more_than_completed(self):
        self.args[0]["observed_archived_shards"]=243
        self.args[1]=copy.deepcopy(self.args[0])
        self.reject()
