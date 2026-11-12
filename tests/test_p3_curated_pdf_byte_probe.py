"""P3 original-PDF byte probe never treats a hash as issuer/PIT proof."""
import copy,io,json,unittest
from pathlib import Path
from unittest.mock import Mock
from collector.p3_curated_pdf_byte_probe import run,probe_one,safe_pdf_url

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/"evidence/p3_eight_issuer_halt_resume_research_refs_20261112.json").read_text())
PDF=b"%PDF-1.7\n"+b"0"*64+b"\n%%EOF\n"

class FakeResponse:
    status=200
    headers={"Content-Length":str(len(PDF))}
    def __init__(self,data=PDF,status=200,headers=None):
        self.status=status
        self.headers=headers or {"Content-Length":str(len(data))}
        self.f=io.BytesIO(data)
    def __enter__(self):return self
    def __exit__(self,*args):self.f.close()
    def read(self,n):return self.f.read(n)

class ProbeTests(unittest.TestCase):
    def setUp(self):self.manifest=copy.deepcopy(MANIFEST)
    def good(self,url,opener):
        x=probe_one(url,opener)
        self.assertFalse(x["official_exchange_pit_certified"])
        return x
    def test_exact_nine_pdf_sources_hashed_without_pit_claim(self):
        opener=Mock(open=Mock(side_effect=lambda *args,**kwargs: FakeResponse()))
        r=run(self.manifest,opener,self.good)
        self.assertEqual(r["approved_pdf_url_count"],9)
        self.assertEqual(r["downloaded_pdf_with_sha_count"],9)
        self.assertEqual(r["failed_or_unavailable_pdf_count"],0)
        self.assertTrue(all(len(x["sha256"])==64 for x in r["pdf_byte_hash_receipts"]))
        self.assertFalse(r["source_pdf_original_bytes_authenticity_certified"])
        self.assertFalse(r["full_historical_exchange_PIT_certified"])
        self.assertEqual(r["source_feature_shards_promoted"],0)
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(opener.open.call_count,9)
    def test_block_fake_hosts_before_http(self):
        opener=Mock(open=Mock(side_effect=AssertionError("network must not run")))
        for bad in ("http://static.cninfo.com.cn/finalpage/2026-10-19/1.PDF",
                    "https://static.cninfo.com.cn.evil.net/finalpage/2026-10-19/1.PDF",
                    "https://static.cninfo.com.cn/finalpage/2026-10-19/1.PDF?x=1",
                    "https://static.cninfo.com.cn/anything.PDF"):
            with self.assertRaises(ValueError):probe_one(bad,opener)
        self.assertEqual(opener.open.call_count,0)
    def test_html_body_not_a_pdf_hash(self):
        opener=Mock(open=Mock(return_value=FakeResponse(b"<html>"*20)))
        one=probe_one(MANIFEST["cases"][0]["documents"][0]["url"],opener)
        self.assertEqual(one["fetch_outcome"],"NOT_VALID_PDF_ENVELOPE")
        self.assertIsNone(one["sha256"])
    def test_missing_eof_rejected(self):
        opener=Mock(open=Mock(return_value=FakeResponse(b"%PDF-1.7"+b"x"*128)))
        one=probe_one(MANIFEST["cases"][0]["documents"][0]["url"],opener)
        self.assertIsNone(one["sha256"])
    def test_content_length_oversize_blocks_hash(self):
        opener=Mock(open=Mock(return_value=FakeResponse(PDF,headers={"Content-Length":str(20_000_000)})))
        one=probe_one(MANIFEST["cases"][0]["documents"][0]["url"],opener)
        self.assertEqual(one["fetch_outcome"],"OVER_SIZE_OR_INVALID_LENGTH")
    def test_server_unavailable_preserved_as_unknown(self):
        opener=Mock(open=Mock(side_effect=TimeoutError("timeout")))
        result=run(self.manifest,opener)
        self.assertEqual(result["failed_or_unavailable_pdf_count"],9)
        self.assertEqual(result["downloaded_pdf_with_sha_count"],0)
    def test_input_fake_verified_sha_rejected(self):
        self.manifest["cases"][0]["documents"][0]["content_sha256"]="f"*64
        with self.assertRaises(ValueError):run(self.manifest,Mock())
    def test_extra_unreviewed_pdf_rejected(self):
        self.manifest["cases"][0]["documents"].append({
            "reference_class":"issuer_pdf_indexed",
            "url":"https://static.cninfo.com.cn/finalpage/2026-10-19/888.PDF",
            "content_sha256":None,
            "announcement":"forged","date":"2026-10-19"
        })
        opener=Mock(open=Mock(return_value=FakeResponse()))
        with self.assertRaises(ValueError):run(self.manifest,opener)
    def test_duplicate_pdf_rejected(self):
        self.manifest["cases"][1]["documents"][1]["url"]=self.manifest["cases"][0]["documents"][0]["url"]
        opener=Mock(open=Mock(return_value=FakeResponse()))
        with self.assertRaises(ValueError):run(self.manifest,opener)
    def test_manifest_trade_gate_must_remain_blocked(self):
        self.manifest["trade_gate"]="OPEN"
        with self.assertRaises(ValueError):run(self.manifest,Mock())
    def test_non200_is_unavailable_not_pdf(self):
        opener=Mock(open=Mock(return_value=FakeResponse(status=403)))
        one=probe_one(MANIFEST["cases"][0]["documents"][0]["url"],opener)
        self.assertEqual(one["fetch_outcome"],"NON_200_HTTP")
        self.assertIsNone(one["sha256"])
