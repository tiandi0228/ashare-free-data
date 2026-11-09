import copy
import unittest
from collector.p2_p3_current_source_guard import validate_sources

EPOCH="a"*64

def samples():
    coverage={"phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
              "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
              "source_epoch_sha256":EPOCH,"trade_gate":"BLOCKED","orders":[],
              "historical_PIT_verified":False,"coverage_certified_for_trading":False,
              "full_archive_evidence_accounted":True,"unobserved_archived_shards":0,
              "unobserved_issuer_count":0,"observed_archived_shards":20,
              "gap_issuer_codes":["sh.600001","sh.600002"],
              "issuer_evidence_gap_count":2}
    gaps={"phase":"P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS",
          "status":"SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY",
          "source_epoch_sha256":EPOCH,"trade_gate":"BLOCKED","orders":[],
          "historical_PIT_verified":False,"coverage_gaps_resolved":0,
          "historical_halt_intervals_certified":0,
          "research_gap_issuers":2,
          "results":[{"issuer":"sh.600001"},{"issuer":"sh.600002"}]}
    queue={"roster_source_sha256":EPOCH,
           "historical_PIT_verified":False,"trade_gate":"BLOCKED","orders":[]}
    return gaps,coverage,queue


class SameEpochCrosswalkGuardTests(unittest.TestCase):
    def test_valid_source_run_provenance_is_research_only(self):
        out=validate_sources(*samples(),101,202)
        self.assertEqual(out["source_epoch_sha256"],EPOCH)
        self.assertEqual(out["issuer_codes"],["sh.600001","sh.600002"])
        self.assertEqual(out["p2_source_run_id"],101)
        self.assertEqual(out["p3_source_run_id"],202)
        self.assertFalse(out["historical_PIT_verified"])
        self.assertEqual(out["trade_gate"],"BLOCKED")
        self.assertEqual(out["orders"],[])

    def test_stale_gap_records_or_cross_epoch_p3_fail_closed(self):
        for i,key,value in (
            (0,"source_epoch_sha256","b"*64),
            (2,"roster_source_sha256","c"*64),
            (1,"issuer_evidence_gap_count",1),
            (0,"research_gap_issuers",1),
            (1,"gap_issuer_codes",["sh.600001"]),
            (1,"gap_issuer_codes",["sh.600002","sh.600001"]),
            (1,"full_archive_evidence_accounted",False),
            (1,"unobserved_archived_shards",1),
        ):
            arr=list(copy.deepcopy(samples()))
            arr[i][key]=value
            with self.subTest(source=i,key=key),self.assertRaises(ValueError):
                validate_sources(*arr,101,202)

    def test_duplicate_or_forged_official_certification_rejected(self):
        for i,key,value in (
            (0,"historical_PIT_verified",True),
            (1,"coverage_certified_for_trading",True),
            (2,"historical_PIT_verified",True),
            (2,"trade_gate","OPEN"),
            (0,"orders",[{"pretend":"buy"}]),
        ):
            arr=list(copy.deepcopy(samples()))
            arr[i][key]=value
            with self.subTest(source=i,key=key),self.assertRaises(ValueError):
                validate_sources(*arr,101,202)
        a,b,c=samples()
        a["results"][1]["issuer"]="sh.600001"
        with self.assertRaises(ValueError):
            validate_sources(a,b,c,101,202)

    def test_unverified_or_missing_actions_run_not_promoted(self):
        for id1,id2 in ((0,5),(5,0),(-1,2),(True,2),(2,False)):
            with self.subTest(id1=id1,id2=id2),self.assertRaises(ValueError):
                validate_sources(*samples(),id1,id2)


if __name__=="__main__":
    unittest.main()
