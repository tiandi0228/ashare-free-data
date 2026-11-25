"""Three issuer source references cannot turn vendor halt flags into official PIT."""
import copy
import json
import unittest
from pathlib import Path
from collector.p3_three_issuer_halt_source_crosswalk import crosswalk,SHAS
from collector.p2_original_gap_action_triage import triage
from tests.test_p2_original_gap_action_triage import fixture

SOURCE=Path(__file__).resolve().parents[1]/"evidence/p3_issuer_halt_resume_three_research_refs.json"
def make():
    x=fixture()
    for item,code in zip(x["gap_repair_queue"][0]["issuer_reasons"],("sh.600293","sh.600301")):
        shard,sha,count=SHAS[code]
        item["issuer"]=code
        item["original_gap_diagnostic"]["original_csv_sha256"]=sha
        item["original_gap_diagnostic"]["last_21_vendor_rows_suspended"]=count
    item=x["gap_repair_queue"][8]["issuer_reasons"][0]
    shard,sha,count=SHAS["sh.603400"]
    item["issuer"]="sh.603400"
    item["original_gap_diagnostic"]["original_csv_sha256"]=sha
    item["original_gap_diagnostic"]["last_21_vendor_rows_suspended"]=count
    return triage(x),json.loads(SOURCE.read_text())

class ThreeIssuerTests(unittest.TestCase):
    def setUp(self):
        self.g,self.s=make()
    def reject(self):
        with self.assertRaises(ValueError):crosswalk(self.g,self.s)

    def test_three_sources_conservative(self):
        a=crosswalk(self.g,self.s)
        self.assertEqual(a["reviewed_issuer_count"],3)
        self.assertEqual(a["remaining_vendor_suspension_issuer_count"],12)
        self.assertEqual(a["remaining_all_gap_issuer_count"],16)
        self.assertEqual(a["research_feature_complete_shards"],226)
        self.assertEqual(a["feature_shards_promoted"],0)
        self.assertIs(a["historical_PIT_verified"],False)
        self.assertEqual(a["trade_gate"],"BLOCKED")
    def test_halt_resume_dates(self):
        a=crosswalk(self.g,self.s)
        self.assertEqual(a["referenced_issuers"]["sh.600293"]["resume_day_claim"],"2026-10-20")
        self.assertEqual(a["referenced_issuers"]["sh.600301"]["resume_day_claim"],"2026-09-21")
        self.assertEqual(a["referenced_issuers"]["sh.603400"]["halt_start_claim"],"2026-09-15")
    def test_no_pdf_byte_authentication_forgery(self):
        self.s["pdf_original_bytes_sha_verified_in_this_audit"]=True
        self.reject()
    def test_no_official_publisher_forgery(self):
        self.s["publisher_origin_independently_authenticated"]=True
        self.reject()
    def test_reject_vendor_original_sha_drift(self):
        self.g["research_actions"][0]["original_csv_sha256"]="a"*64
        self.reject()
    def test_reject_supplier_halt_count_drift(self):
        self.g["research_actions"][0]["suspended_rows_last_21"]=9
        self.reject()
    def test_reject_announcement_date_forgery(self):
        self.s["pairs"][0]["docs"][0]["date"]="2026-09-30"
        self.reject()
    def test_reject_unexpected_pdf_url(self):
        self.s["pairs"][1]["docs"][0]["url"]="https://example.com/other.pdf"
        self.reject()
    def test_reject_pit_provenance_forgery(self):
        self.g["historical_PIT_verified"]=True
        self.reject()
    def test_reject_duplicate_company(self):
        self.s["pairs"][1]["issuer"]="sh.600293"
        self.reject()
    def test_reject_gap_promotion(self):
        self.g["research_actions"][0]["gap_resolved"]=True
        self.reject()
    def test_reject_unblocked_orders(self):
        self.s["orders"]=[{"symbol":"600293"}]
        self.reject()
