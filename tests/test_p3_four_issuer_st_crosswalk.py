"""P3 four dated issuer source references and ST issuer risk gate."""
import json
import unittest
from pathlib import Path
from collector.p3_four_issuer_st_crosswalk import reconcile, EXPECTED
from collector.p2_original_gap_action_triage import triage
from tests.test_p2_original_gap_action_triage import fixture

SOURCES=Path(__file__).resolve().parents[1]/"evidence/p3_four_issuer_halt_st_research_refs.json"
SHARD_MAP={"sh.600363":1,"sh.600825":2,"sh.603159":6,"sh.605303":12}

def inputs():
    raw=fixture()
    for issuer,index in SHARD_MAP.items():
        shard,sha,num,*_=EXPECTED[issuer]
        row=raw["gap_repair_queue"][index]["issuer_reasons"][0]
        assert row["original_gap_diagnostic"]["category"]=="VENDOR_SUSPENDED_IN_LAST_21_ROWS"
        row["issuer"]=issuer
        row["original_gap_diagnostic"]["original_csv_sha256"]=sha
        row["original_gap_diagnostic"]["last_21_vendor_rows_suspended"]=num
    return triage(raw),json.loads(SOURCES.read_text())

class FourIssuerTests(unittest.TestCase):
    def setUp(self):
        self.g,self.s=inputs()

    def should_reject(self):
        with self.assertRaises(ValueError):reconcile(self.g,self.s)

    def test_four_linked_and_eight_left(self):
        r=reconcile(self.g,self.s)
        self.assertEqual(r["new_issuer_sources_linked"],4)
        self.assertEqual(r["total_vendor_suspension_issuer_sources_linked"],7)
        self.assertEqual(r["remaining_vendor_suspension_issuers_without_source_links"],8)
        self.assertEqual(r["feature_complete_shards"],226)
        self.assertEqual(r["original_gap_issuers_unresolved"],16)
        self.assertEqual(r["feature_shards_promoted"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_st_600363_disallowed_non_st_strategy_from_9_30(self):
        r=reconcile(self.g,self.s)
        self.assertEqual(r["st_risk_exclusion"]["issuer"],"sh.600363")
        self.assertEqual(r["st_risk_exclusion"]["effective_from"],"2026-09-30")
        self.assertFalse(r["st_risk_exclusion"]["non_st_mainboard_screen_allowed_from_effective_day"])
        self.assertFalse(r["issuer_source_pdf_bytes_sha_verified"])

    def test_no_st_date_forgery(self):
        self.s["cases"][0]["st_start"]="2026-10-01"
        self.should_reject()

    def test_no_st_name_forgery(self):
        self.s["cases"][0]["st_name"]="联创光电"
        self.should_reject()

    def test_no_pdf_sha_certification_forgery(self):
        self.s["source_documents_pdf_bytes_sha_verified"]=True
        self.should_reject()

    def test_no_pit_certification(self):
        self.g["historical_PIT_verified"]=True
        self.should_reject()

    def test_no_original_csv_drift(self):
        next(x for x in self.g["research_actions"] if x["issuer"]=="sh.600363")["original_csv_sha256"]="a"*64
        self.should_reject()

    def test_no_issuer_swap(self):
        self.s["cases"][1]["issuer"]="sh.600363"
        self.should_reject()

    def test_no_wrong_halt_date(self):
        self.s["cases"][2]["halt_start"]="2026-09-11"
        self.should_reject()

    def test_no_resumption_date_forgery(self):
        self.s["cases"][3]["resume_day"]="2026-09-30"
        self.should_reject()

    def test_no_url_swap(self):
        self.s["cases"][1]["documents"][1]["url"]="https://example.net/invalid.pdf"
        self.should_reject()

    def test_no_feature_promotion(self):
        self.g["research_actions"][2]["eligible_for_feature_complete_promotion"]=True
        self.should_reject()

    def test_no_orders(self):
        self.s["orders"]=[{"code":"600363"}]
        self.should_reject()

    def test_no_trade_gate_open(self):
        self.s["trade_gate"]="OPEN"
        self.should_reject()
