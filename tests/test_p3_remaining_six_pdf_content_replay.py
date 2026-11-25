"""Remaining six P3 PDF evidence checks are never PIT certification."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import Mock
from collector.p3_remaining_six_pdf_content_replay import audit,TARGETS
from collector.p3_curated_pdf_byte_probe import PHASE as FIRST_PHASE
from collector.p3_pdf_content_anchor_replay import normalized

M=json.loads((Path(__file__).resolve().parents[1]/
    "evidence/p3_eight_issuer_halt_resume_research_refs_20261112.json").read_text())
DIGEST="a"*64
def fixture():
    rows=[]
    for case in M["cases"]:
        for d in case["documents"]:
            if d["reference_class"]=="issuer_pdf_indexed":
                rows.append({"url":d["url"],"sha256":DIGEST,
                    "fetch_outcome":"PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED"})
    assert len(rows)==9
    return [copy.deepcopy(M),{"phase":FIRST_PHASE,
        "source_epoch_sha256":M["source_epoch_sha256"],"trade_gate":"BLOCKED",
        "full_historical_exchange_PIT_certified":False,"pdf_byte_hash_receipts":rows}]
def good(url,digest,opener,pdf_to_text):
    for case in M["cases"]:
        for doc in case["documents"]:
            if doc["url"]==url:
                key=(case["issuer"],doc["announcement"])
                assert key in TARGETS
                company,term=TARGETS[key]
                text=(company+" 证券代码"+key[0].split(".")[1]+" 公告编号"
                     +key[1].removeprefix("临")+" 股票"+term)
                return {"second_read_sha256":digest,
                        "same_bytes_as_first_read":True,"text_extracted":True,
                        "normalized_text":normalized(text),
                        "status":"MATCHING_SHA_PDF_TEXT_EXTRACTED_NOT_PIT_CERTIFIED"}
    raise AssertionError("missing URL")

class RemainingPDFTests(unittest.TestCase):
    def setUp(self):self.args=fixture()
    def run_replay(self,download=good):return audit(*self.args,Mock(),download=download)
    def reject(self):
        with self.assertRaises(ValueError):self.run_replay()
    def test_six_original_sources_all_anchor(self):
        o=self.run_replay()
        self.assertEqual(o["remaining_original_pdf_count"],6)
        self.assertEqual(o["two_read_sha_matching_count"],6)
        self.assertEqual(o["issuer_company_notice_term_text_matched_count"],6)
        self.assertEqual(len(o["rows"]),6)
        self.assertFalse(o["historical_PIT_verified"])
        self.assertEqual(o["feature_shards_promoted"],0)
        self.assertEqual(o["trade_gate"],"BLOCKED")
    def test_mismatched_url_identity_rejected(self):
        self.args[1]["pdf_byte_hash_receipts"][0]["url"]="https://static.cninfo.com.cn/finalpage/2026-09-15/3333333333.PDF"
        self.reject()
    def test_duplicate_source_notice_rejected(self):
        self.args[0]["cases"][0]["documents"][1]["announcement"]="2026-049"
        self.reject()
    def test_missing_pdf_receipt_rejected(self):
        self.args[1]["pdf_byte_hash_receipts"].pop()
        self.reject()
    def test_invalid_sha_rejected(self):
        self.args[1]["pdf_byte_hash_receipts"][0]["sha256"]="bad"
        self.reject()
    def test_wrong_epoch_rejected(self):
        self.args[1]["source_epoch_sha256"]="b"*64
        self.reject()
    def test_trade_gate_promotion_rejected(self):
        self.args[0]["trade_gate"]="OPEN"
        self.reject()
    def test_changed_second_pdf_never_certified(self):
        def changed(url,digest,*args):
            return {"second_read_sha256":"f"*64,"same_bytes_as_first_read":False,
                    "text_extracted":False,"normalized_text":None,
                    "status":"SOURCE_PDF_BYTES_CHANGED_BETWEEN_READS"}
        o=self.run_replay(changed)
        self.assertEqual(o["two_read_sha_matching_count"],0)
        self.assertEqual(o["issuer_company_notice_term_text_matched_count"],0)
    def test_forged_second_sha_equality_rejected(self):
        def forged(url,digest,*args):
            return {"second_read_sha256":"f"*64,"same_bytes_as_first_read":True,
                    "text_extracted":True,"normalized_text":"fake"}
        with self.assertRaises(ValueError):self.run_replay(forged)
    def test_missing_research_term_denied(self):
        def missing(url,digest,opener,pdf):
            d=good(url,digest,opener,pdf)
            d["normalized_text"]=d["normalized_text"].replace("复牌","other").replace("停牌","other")
            return d
        o=self.run_replay(missing)
        self.assertEqual(o["two_read_sha_matching_count"],6)
        self.assertEqual(o["issuer_company_notice_term_text_matched_count"],0)
    def test_company_mismatch_not_accepted(self):
        def bad(url,digest,opener,pdf):
            d=good(url,digest,opener,pdf)
            d["normalized_text"]=d["normalized_text"].replace("星帅尔","其他公司")
            return d
        self.assertEqual(self.run_replay(bad)["issuer_company_notice_term_text_matched_count"],4)
