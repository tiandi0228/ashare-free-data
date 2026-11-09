import copy
import unittest

from collector.p2_p3_issuer_proof_action_queue import build,CATEGORIES

EPOCH="a"*64


def sample():
    codes=["sh.600001","sh.600002","sh.600003","sh.600004"]
    data=[
        ("VENDOR_SUSPENDED_ROW_WITHIN_LAST_21",0,0),
        ("VENDOR_SUSPENDED_ROW_WITHIN_LAST_21",2,0),
        ("VENDOR_SUSPENDED_ROW_WITHIN_LAST_21",3,1),
        ("FEWER_THAN_21_VENDOR_ROWS_ASOF",0,0),
    ]
    rows=[]
    for issuer,(diag,leads,pairs) in zip(codes,data):
        rows.append({
            "issuer":issuer,"vendor_gap_diagnosis":diag,
            "vendor_csv_sha256":"b"*64,
            "same_issuer_official_pdf_text_leads":leads,
            "same_issuer_sha_linked_resume_text_pairs":pairs,
            "official_trading_state_covered_for_gap":False,
            "gap_resolved":False,
        })
    crosswalk={
        "phase":"P2_P3_SAME_ISSUER_RESEARCH_GAP_CROSSWALK",
        "source_epoch_sha256":EPOCH,
        "status":"RESEARCH_JOIN_NO_PIT_EVENT_CAUSATION",
        "gap_issuers_examined":4,
        "gap_issuers_with_same_issuer_official_pdf_text_lead":2,
        "gap_issuers_with_same_issuer_resume_text_pair":1,
        "issuer_evidence":rows,
        "official_halt_intervals_authenticated":0,
        "feature_gaps_resolved":0,"historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "actionable_buy_signals":[],
    }
    guard={
        "phase":"P2_P3_CURRENT_RESEARCH_SOURCE_CROSSWALK_GUARD",
        "status":"SAME_P1_EPOCH_SOURCE_BOUNDED_RESEARCH_ONLY",
        "source_epoch_sha256":EPOCH,
        "p2_source_run_id":100,"p3_source_run_id":200,
        "p2_current_archived_shards":197,
        "p2_vendor_gap_issuers":4,
        "issuer_codes":codes,
        "P3_event_text_is_official_halt_authentication":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }
    return crosswalk,guard


class SourceEvidenceActionQueueTests(unittest.TestCase):
    def test_exact_issuer_actions_without_any_tradable_claim(self):
        report=build(*sample())
        self.assertEqual(report["gap_issuer_count"],4)
        self.assertEqual(report["review_action_counts"],dict.fromkeys(CATEGORIES,1))
        self.assertEqual(report["issuer_with_same_issuer_text_lead"],2)
        self.assertEqual(report["issuer_with_resume_text_pair"],1)
        self.assertEqual(report["p1_completed_shards_in_source_scope"],197)
        self.assertEqual(report["source_epoch_sha256"],EPOCH)
        self.assertEqual(len({x["issuer"] for x in report["tasks"]}),4)
        self.assertFalse(report["historical_PIT_verified"])
        self.assertEqual(report["official_halt_intervals_certified"],0)
        self.assertEqual(report["feature_gaps_resolved"],0)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])
        self.assertEqual(report["actionable_buy_signals"],[])
        self.assertTrue(all(x["feature_gap_resolved"] is False
                            and x["buy_eligible"] is False
                            and x["official_evidence_authenticated"] is False
                            for x in report["tasks"]))

    def test_source_issuer_or_count_mismatches_fail_closed(self):
        for index,key,value in (
            (0,"gap_issuers_examined",3),
            (0,"gap_issuers_with_same_issuer_official_pdf_text_lead",3),
            (0,"gap_issuers_with_same_issuer_resume_text_pair",2),
            (1,"p2_vendor_gap_issuers",3),
            (1,"source_epoch_sha256","c"*64),
            (1,"issuer_codes",["sh.600001","sh.600002"]),
            (0,"trade_gate","OPEN"),
            (1,"trade_gate","OPEN"),
        ):
            args=list(copy.deepcopy(sample()));args[index][key]=value
            with self.subTest(index=index,key=key),self.assertRaises(ValueError):
                build(*args)

    def test_forged_issuer_certification_or_invalid_digest_rejected(self):
        for key,value in (
            ("gap_resolved",True),
            ("official_trading_state_covered_for_gap",True),
            ("vendor_csv_sha256","NOT-SHA"),
            ("same_issuer_official_pdf_text_leads",-1),
            ("same_issuer_sha_linked_resume_text_pairs",True),
            ("issuer","sh.603999"),
        ):
            cw,guard=copy.deepcopy(sample())
            cw["issuer_evidence"][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                build(cw,guard)

    def test_unmatched_resume_text_pairs_remain_uncertified(self):
        cw,guard=sample()
        row=cw["issuer_evidence"][0]
        row["same_issuer_sha_linked_resume_text_pairs"]=1
        cw["gap_issuers_with_same_issuer_resume_text_pair"]=2
        result=build(cw,guard)
        item=next(x for x in result["tasks"] if x["issuer"]=="sh.600001")
        self.assertEqual(item["research_action"],CATEGORIES[3])
        self.assertFalse(item["official_evidence_authenticated"])
        self.assertFalse(item["historical_PIT_verified"])

    def test_corrupt_crosswalk_empty_or_duplicated_issuers_rejected(self):
        cw,guard=sample()
        cw["issuer_evidence"][1]["issuer"]="sh.600001"
        with self.assertRaises(ValueError):build(cw,guard)
        cw,guard=sample()
        cw["issuer_evidence"]=[]
        with self.assertRaises(ValueError):build(cw,guard)


if __name__=="__main__":
    unittest.main()
