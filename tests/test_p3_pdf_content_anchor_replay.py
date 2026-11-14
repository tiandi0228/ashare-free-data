"""P3 priority PDF text anchors are research-only, never a PIT approval."""
import copy
import hashlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock
from collector.p3_pdf_content_anchor_replay import (
    evaluate,download_same_pdf,normalized,PRIORITY
)
from collector.p3_curated_pdf_byte_probe import PHASE as BYTE_PHASE

ROOT=Path(__file__).resolve().parents[1]
M=json.loads((ROOT/"evidence/p3_eight_issuer_halt_resume_research_refs_20261112.json").read_text())
RAW=b"%PDF-1.7\n"+b"0"*128+b"\n%%EOF\n"
SHA=hashlib.sha256(RAW).hexdigest()
TEXT={
 "sh.601238":"广汽集团 股票代码601238 公告编号2026-049 股票停牌 2026年9月14日 2026年9月15日",
 "sh.603517":"绝味食品 证券代码603517 公告编号2026-080 撤销其他风险警示 2026年10月20日",
 "sh.603838":"四通股份 证券代码603838 公告编号2026-040 撤销风险警示 2026年10月20日",
}
def fixture():
    receipts=[]
    for case in M["cases"]:
        for d in case["documents"]:
            if d["reference_class"]=="issuer_pdf_indexed":
                receipts.append({"url":d["url"],"sha256":SHA,
                    "fetch_outcome":"PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED"})
    assert len(receipts)==9
    return [copy.deepcopy(M),{"phase":BYTE_PHASE,
        "source_epoch_sha256":M["source_epoch_sha256"],"trade_gate":"BLOCKED",
        "source_pdf_original_bytes_authenticity_certified":False,
        "full_historical_exchange_PIT_certified":False,
        "pdf_byte_hash_receipts":receipts}]

class Response:
    status=200
    headers={"Content-Length":str(len(RAW))}
    def __init__(self,data=RAW):
        self.fp=io.BytesIO(data)
    def __enter__(self):return self
    def __exit__(self,*args):self.fp.close()
    def read(self,n):return self.fp.read(n)

def good_download(url,sha,opener,pdf_to_text):
    issuer=next(c["issuer"] for c in M["cases"]
      if any(d["url"]==url for d in c["documents"]))
    return {"url":url,"same_bytes_as_first_read":True,
      "text_extracted":True,"second_read_sha256":sha,
      "normalized_text":normalized(TEXT[issuer]),
      "status":"MATCHING_SHA_PDF_TEXT_EXTRACTED_NOT_PIT_CERTIFIED"}

class AnchorTests(unittest.TestCase):
    def setUp(self):self.args=fixture()
    def audit(self,download=good_download):
        return evaluate(*self.args,Mock(),download=download)
    def test_three_priority_issuer_notice_content_observed(self):
        r=self.audit()
        self.assertEqual(r["priority_issuer_count"],3)
        self.assertEqual(r["same_bytes_twice_count"],3)
        self.assertEqual(r["issuer_notice_and_term_text_observed_count"],3)
        self.assertTrue(r["guangqi_conflicting_halt_date_unresolved"])
        self.assertEqual(r["rows"][0]["halt_effective_day_status"],
                         "UNRESOLVED_CONFLICT_REQUIRES_EXCHANGE_DAY_PROOF")
        self.assertTrue(r["rows"][0]["has_2026_september_14_claim"])
        self.assertTrue(r["rows"][0]["has_2026_september_15_claim"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])
    def test_source_csv_sha_preserved_for_each_issuer(self):
        r=self.audit()
        src={c["issuer"]:c["original_csv_sha256"] for c in M["cases"]}
        for row in r["rows"]:
            self.assertEqual(row["source_original_csv_sha256"],src[row["issuer"]])
    def test_second_pdf_changed_sha_is_not_text_certified(self):
        def changed(url,sha,opener,pdf_to_text):
            return {"url":url,"same_bytes_as_first_read":False,
                "text_extracted":False,"normalized_text":None,
                "second_read_sha256":"f"*64,"status":"SOURCE_PDF_BYTES_CHANGED_BETWEEN_READS"}
        r=self.audit(changed)
        self.assertEqual(r["issuer_notice_and_term_text_observed_count"],0)
        self.assertEqual(r["same_bytes_twice_count"],0)
    def test_missing_announcement_number_cannot_claim_anchor(self):
        def bad(url,sha,opener,pdf_to_text):
            x=good_download(url,sha,opener,pdf_to_text)
            x["normalized_text"]=x["normalized_text"].replace("2026-080","unknown")
            return x
        r=self.audit(bad)
        self.assertEqual(r["issuer_notice_and_term_text_observed_count"],2)
        self.assertFalse(r["rows"][1]["announcement_number_anchor"])
        self.assertFalse(r["rows"][1]["issuer_and_notice_text_observed"])
    def test_old_st_cannot_be_promoted_by_matching_document(self):
        r=self.audit()
        for row in r["rows"][1:]:
            self.assertEqual(row["st_lookback_status"],"REJECT_PRE_REMOVAL_AS_ELIGIBLE")
            self.assertFalse(row["historical_ST_period_certified"])
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["feature_shards_promoted"],0)
    def test_first_probe_malformed_sha_denied(self):
        for receipt in self.args[1]["pdf_byte_hash_receipts"]:
            if "1225609996" in receipt["url"]:
                receipt["sha256"]="bad"
        def no(url,sha,opener,pdf_to_text):
            raise AssertionError("invalid digest cannot reach network")
        with self.assertRaises(ValueError):
            self.audit(no)
    def test_unsupported_first_probe_claim_fails(self):
        self.args[1]["full_historical_exchange_PIT_certified"]=True
        with self.assertRaises(ValueError):self.audit()
    def test_missing_first_pdf_receipt_fails(self):
        self.args[1]["pdf_byte_hash_receipts"].pop()
        with self.assertRaises(ValueError):self.audit()
    def test_original_manifest_trading_gate_fails(self):
        self.args[0]["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):self.audit()
    def test_bounded_double_fetch_digest_matches(self):
        opener=Mock(open=Mock(return_value=Response()))
        url=M["cases"][3]["documents"][0]["url"]
        output=download_same_pdf(url,SHA,opener,lambda raw:TEXT["sh.603517"])
        self.assertTrue(output["same_bytes_as_first_read"])
        self.assertTrue(output["text_extracted"])
        self.assertIn("603517",output["normalized_text"])
        self.assertFalse(output.get("official_PIT_session_authenticated",False))
    def test_mismatched_double_fetch_never_extracts_text(self):
        opener=Mock(open=Mock(return_value=Response()))
        url=M["cases"][3]["documents"][0]["url"]
        extract=Mock(side_effect=AssertionError("must not parse changed PDF"))
        output=download_same_pdf(url,"a"*64,opener,extract)
        self.assertEqual(output["status"],"SOURCE_PDF_BYTES_CHANGED_BETWEEN_READS")
        self.assertEqual(extract.call_count,0)
    def test_html_response_not_pdf(self):
        opener=Mock(open=Mock(return_value=Response(b"<html>not a PDF</html>")))
        url=M["cases"][3]["documents"][0]["url"]
        output=download_same_pdf(url,SHA,opener,lambda b:"wrong")
        self.assertFalse(output["same_bytes_as_first_read"])
        self.assertIsNone(output["second_read_sha256"])
