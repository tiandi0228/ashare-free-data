import copy
import json
import tempfile
import unittest
from pathlib import Path

from collector.p3_archived_visit_hint import build
from collector.p3_full_queue_scout import plan
from tests.test_p3_full_queue_scout import q,p2_source_hint

EPOCH="b"*64
DIGEST="a"*64


def manifest(number,epoch,issuer,retrieved=True):
    row={
        "issuer":issuer,"announcement_id":"123456789",
        "historical_PIT_verified":False,
        "historical_first_publication_authenticated":False,
        "effective_date_authenticated":False,
        "original_retrieved":retrieved,
    }
    if retrieved:
        row["pdf_sha256"]=DIGEST
        row["archive_path"]=f"pdf/{issuer.replace('.', '_')}/123456789/{DIGEST}.pdf"
    return {
        "phase":"P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE",
        "run_id":number,"source_roster_sha256":epoch,
        "source_pdf_receipts":[row],
        "original_pdf_count":int(retrieved),
        "certified_first_publication_count":0,
        "certified_event_effective_day_count":0,
        "certified_historical_decision_state_count":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def write_manifest(root,number,epoch,issuer,retrieved=True):
    out=Path(root)/"runs";out.mkdir(exist_ok=True)
    (out/f"{number}.json").write_text(json.dumps(
        manifest(number,epoch,issuer,retrieved)))


def four_issuer_p2_hint():
    hint=p2_source_hint(issuer="sh.600000",shard_id="shard_0000")
    for index,issuer in enumerate(("sz.000001","sz.000002","sh.600003"),1):
        row=copy.deepcopy(hint["gap_repair_queue"][0])
        row["shard_id"]=f"shard_{index:04d}"
        row["issuer_reasons"][0]["issuer"]=issuer
        hint["gap_repair_queue"].append(row)
    hint["observed_with_feature_gaps_shards"]=4
    hint["issuer_evidence_gap_count"]=4
    return hint


class P3ArchivedResearchVisitTests(unittest.TestCase):
    def test_immutable_run_receipts_distinguish_attempted_and_retrieved(self):
        with tempfile.TemporaryDirectory() as d:
            write_manifest(d,10,EPOCH,"sh.600000")
            write_manifest(d,11,EPOCH,"sh.600000",retrieved=False)
            write_manifest(d,12,EPOCH,"sz.000001")
            write_manifest(d,13,"c"*64,"sh.600000")
            result=build(d,EPOCH)
            self.assertEqual(result["matching_archive_run_manifests"],3)
            self.assertEqual(result["issuer_visit_counts"],
                             {"sh.600000":2,"sz.000001":1})
            self.assertEqual(result["issuer_original_retrieval_counts"],
                             {"sh.600000":1,"sz.000001":1})
            self.assertFalse(result["historical_PIT_verified"])
            self.assertFalse(result["official_history_search_exhaustive"])
            self.assertEqual(result["orders"],[])

    def test_unsafe_manifest_and_fake_original_sha_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            write_manifest(d,10,EPOCH,"sh.600000")
            path=Path(d)/"runs/10.json"
            original=json.loads(path.read_text())
            for mutate in (
                lambda m:m.update(trade_gate="OPEN"),
                lambda m:m.update(certified_first_publication_count=1),
                lambda m:m["source_pdf_receipts"][0].update(pdf_sha256="x"*64),
                lambda m:m["source_pdf_receipts"][0].update(historical_PIT_verified=True),
                lambda m:m.update(original_pdf_count=0),
            ):
                m=copy.deepcopy(original);mutate(m);path.write_text(json.dumps(m))
                with self.assertRaises(ValueError):
                    build(d,EPOCH)

    def test_research_visits_prefer_not_yet_attempted_sha_matched_issuer(self):
        with tempfile.TemporaryDirectory() as d:
            for i,code in ((10,"sh.600000"),(11,"sz.000001"),(12,"sz.000002")):
                write_manifest(d,i,EPOCH,code)
            hint=build(d,EPOCH)
            result=plan(q(),p2_coverage=four_issuer_p2_hint(),
                        rotation_index=1,visited_hint=hint)
            selected=[x["issuer"] for x in result["targets"]]
            self.assertEqual(selected[0],"sh.600003")
            self.assertEqual(result["targets"][0]["prior_archived_scout_attempts"],0)
            self.assertEqual(result["targets"][0]["prior_archived_pdf_retrievals"],0)
            self.assertTrue(result["archive_visit_hint_present"])
            self.assertFalse(result["archive_visit_hint_is_official_proof"])
            self.assertFalse(result["official_PIT_verified"])
            self.assertEqual(result["trade_gate"],"BLOCKED")
            self.assertEqual(result["orders"],[])

    def test_missing_hint_uses_legacy_run_rotation_no_forged_zero_visits(self):
        result=plan(q(),p2_coverage=four_issuer_p2_hint(),rotation_index=2)
        self.assertFalse(result["archive_visit_hint_present"])
        self.assertIsNone(result["targets"][0]["prior_archived_scout_attempts"])
        self.assertEqual(len(result["targets"]),3)

    def test_forged_hint_rejected(self):
        hint={
            "phase":"P3_ARCHIVED_RESEARCH_VISIT_HINT_NOT_OFFICIAL_EVIDENCE",
            "source_roster_sha256":EPOCH,"trade_gate":"BLOCKED",
            "historical_PIT_verified":False,
            "official_history_search_exhaustive":False,
            "source_originals_fully_replayed_in_this_hint":False,
            "orders":[],"executable_candidates":[],
            "matching_archive_run_manifests":1,
            "total_archived_issuer_attempts":1,
            "distinct_attempted_issuers":1,
            "issuer_visit_counts":{"sh.600000":1},
            "issuer_original_retrieval_counts":{"sh.600000":1},
        }
        for key,value in (
            ("source_roster_sha256","c"*64),
            ("trade_gate","OPEN"),
            ("historical_PIT_verified",True),
            ("total_archived_issuer_attempts",10),
            ("issuer_visit_counts",{"sh.600000":False}),
            ("issuer_original_retrieval_counts",{"sh.600000":2}),
        ):
            bad=copy.deepcopy(hint);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                plan(q(),p2_coverage=four_issuer_p2_hint(),
                     rotation_index=1,visited_hint=bad)


if __name__=="__main__":
    unittest.main()
