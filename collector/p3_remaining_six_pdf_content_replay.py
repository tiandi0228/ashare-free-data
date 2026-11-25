"""Remaining six P3 PDF bytes: second SHA and issuer/notice text anchors.

Only URL allowlisted research; never equate text match to issuer signing
authenticity, exchange-level PIT session, or permission to trade.
"""
import argparse,json,re
from pathlib import Path
import urllib.request
from collector.p3_curated_pdf_byte_probe import EPOCH,NeverRedirect,safe_pdf_url
from collector.p3_pdf_content_anchor_replay import download_same_pdf,extractor,normalized

PHASE="P3_REMAINING_SIX_PDF_SHA_BOUND_ISSUER_NOTICE_ANCHORS"
# 9 previously downloaded source PDFs, 3 priority verified in prior workflow:
# this stage checks exactly the six remaining original PDF URLs.
TARGETS={
    ("sh.601238","2026-053"):("广汽集团","复牌"),
    ("sh.601995","临2026-065"):("中金公司","复牌"),
    ("sh.603759","2026-083"):("海天股份","复牌"),
    ("sz.002860","2026-044"):("星帅尔","停牌"),
    ("sz.002860","2026-047"):("星帅尔","复牌"),
    ("sz.002870","2026-068"):("香山股份","停牌"),
}
SKIPPED={
    ("sh.601238","2026-049"),
    ("sh.603517","2026-080"),
    ("sh.603838","2026-040"),
}
def audit(manifest,first,opener,download=download_same_pdf,pdf_to_text=extractor):
    if (manifest.get("phase")!="P3_EIGHT_PREVIOUSLY_UNLINKED_ISSUER_DATED_DISCLOSURE_RESEARCH_V1"
        or manifest.get("source_epoch_sha256")!=EPOCH
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("historical_PIT_verified") is not False
        or first.get("phase")!="P3_CURATED_ISSUER_PDF_BYTE_SHA256_READ_ONLY_PROBE"
        or first.get("source_epoch_sha256")!=EPOCH
        or first.get("trade_gate")!="BLOCKED"
        or first.get("full_historical_exchange_PIT_certified") is not False):
        raise ValueError("source evidence not safe")
    receipts=first.get("pdf_byte_hash_receipts")
    if not isinstance(receipts,list) or len(receipts)!=9:
        raise ValueError("missing nine source PDF receipts")
    index={}
    for x in receipts:
        if not isinstance(x,dict):
            raise ValueError("invalid receipt")
        url=safe_pdf_url(x.get("url"))
        if url in index:raise ValueError("duplicate PDF receipt")
        if (x.get("fetch_outcome")=="PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED"
            and not re.fullmatch(r"[0-9a-f]{64}",x.get("sha256") or "")):
            raise ValueError("hash success without SHA256")
        index[url]=x
    docs={}
    for case in manifest.get("cases",[]):
        issuer=case.get("issuer")
        for d in case.get("documents",[]):
            if d.get("reference_class")!="issuer_pdf_indexed":continue
            key=(issuer,d.get("announcement"))
            if key in docs:raise ValueError("duplicate issuer notice")
            docs[key]={
                "url":safe_pdf_url(d.get("url")),
                "source_csv_sha256":case.get("original_csv_sha256")
            }
    if set(docs)!=set(TARGETS)|SKIPPED:
        raise ValueError("unexpected source PDF membership")
    if {v["url"] for v in docs.values()}!=set(index):
        raise ValueError("source URL identity mismatch")
    rows=[]
    for key,(company,term) in TARGETS.items():
        issuer,notice=key
        doc=docs[key]
        url=doc["url"]
        old=index[url]
        out={
          "issuer":issuer,"announcement":notice,"url":url,
          "original_csv_sha256":doc["source_csv_sha256"],
          "first_sha256":old.get("sha256"),"second_sha256":None,
          "same_sha_twice":False,"text_extracted":False,
          "issuer_code_anchor":False,"company_name_anchor":False,
          "notice_id_anchor":False,"research_term_anchor":False,
          "all_four_anchors_matched":False,
          "disclosure_datetime_authenticated":False,
          "official_exchange_PIT_authenticated":False,
          "trading_allowed":False,
          "status":"FIRST_PDF_UNAVAILABLE",
        }
        if old.get("fetch_outcome")=="PDF_BYTES_HASHED_NOT_CONTENT_AUTHENTICATED":
            evidence=download(url,old["sha256"],opener,pdf_to_text)
            if (evidence.get("same_bytes_as_first_read") is True
                and evidence.get("second_read_sha256")!=old["sha256"]):
                raise ValueError("sha asserted equal but digest changed")
            txt=evidence.get("normalized_text")
            out["second_sha256"]=evidence.get("second_read_sha256")
            out["same_sha_twice"]=evidence.get("same_bytes_as_first_read") is True
            out["text_extracted"]=evidence.get("text_extracted") is True
            out["status"]=evidence.get("status","UNAUTHENTICATED")
            if out["same_sha_twice"] and out["text_extracted"] and isinstance(txt,str):
                out["issuer_code_anchor"]=issuer.split(".")[1] in txt
                out["company_name_anchor"]=normalized(company) in txt
                # '临2026-065' may print as '2026-065' in PDF. For that
                # issuer require code number token, but track prefix separately.
                out["notice_id_anchor"]=normalized(notice.removeprefix("临")) in txt
                out["research_term_anchor"]=normalized(term) in txt
                out["all_four_anchors_matched"]=all(out[k] for k in (
                    "issuer_code_anchor","company_name_anchor","notice_id_anchor",
                    "research_term_anchor"))
        rows.append(out)
    return {
        "phase":PHASE,"source_epoch_sha256":EPOCH,
        "remaining_original_pdf_count":6,
        "two_read_sha_matching_count":sum(x["same_sha_twice"] for x in rows),
        "issuer_company_notice_term_text_matched_count":sum(
            x["all_four_anchors_matched"] for x in rows),
        "first_pdf_references_covered":9,
        "original_feature_gap_issuers_unresolved":16,
        "original_feature_gap_shards_unresolved":15,
        "issuer_signature_authenticated":False,
        "exchange_PIT_trading_calendar_authenticated":False,
        "historical_PIT_verified":False,
        "feature_shards_promoted":0,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "rows":rows,
    }
def main():
    p=argparse.ArgumentParser()
    for arg in ("manifest","first-probe","out"):
        p.add_argument("--"+arg,required=True,type=Path)
    a=p.parse_args()
    op=urllib.request.build_opener(urllib.request.ProxyHandler({}),NeverRedirect())
    res=audit(json.loads(a.manifest.read_text()),json.loads(a.first_probe.read_text()),op)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n")
    print("P3_REMAINING_PDFS_SECOND_SHA_AND_TEXT",json.dumps({
        "same_sha_count":res["two_read_sha_matching_count"],
        "all_four_anchors_count":res["issuer_company_notice_term_text_matched_count"],
        "per_notice":[{"issuer":r["issuer"],"notice":r["announcement"],
            "same_sha":r["same_sha_twice"],
            "text":r["text_extracted"],
            "code":r["issuer_code_anchor"],"company":r["company_name_anchor"],
            "notice_number":r["notice_id_anchor"],"term":r["research_term_anchor"]}
            for r in res["rows"]],"trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
