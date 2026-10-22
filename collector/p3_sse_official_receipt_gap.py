"""Reconcile real SSE official-host source hashes with P3 historical risk scope.

Observed official-host pages evidence the event text, not their historical
intraday publication instant or exhaustive listing/ST/halt status.
"""
import argparse
import json
from pathlib import Path
from collector.p3_historical_evidence_coverage import audit_coverage

EXPECTED = (
    ("DELIST_DECISION_ONLY", "2026-05-22",
     "87406ff9a1bac59c856612fbb8da947593cc4ab779401c6d656dc1399790fa4c", 27955, None),
    ("DELIST_EFFECTIVE_DATE_ANNOUNCED", "2026-06-22",
     "d5c80ca0800759ec3f0ffafdf6643dada32bee8a4b4be7bff30cd133887784e8", 26422, "2026-06-26"),
)
DAYS=["2026-05-22","2026-05-23","2026-05-29","2026-06-01",
      "2026-06-19","2026-06-22","2026-06-26"]

def reconcile(receipt):
    if (receipt.get("phase")!="P3_SSE_TWO_OFFICIAL_HOST_DOCUMENTS_OBSERVED"
        or receipt.get("source_run_id")!=39704160169
        or receipt.get("source_job_id")!=119580127889
        or receipt.get("issuer")!="sh.600421"
        or receipt.get("status")!="TWO_OFFICIAL_HOST_DOCUMENTS_OBSERVED_NO_PIT_CERTIFICATION"
        or receipt.get("publisher_digital_signature_verified") is not False
        or receipt.get("historical_intraday_publication_verified") is not False
        or receipt.get("raw_original_html_durably_archived") is not False
        or receipt.get("full_market_PIT_ST_halt_delist_complete") is not False
        or receipt.get("trade_gate")!="BLOCKED"
        or receipt.get("orders")!=[] or receipt.get("executable_candidates")!=[]
        or receipt.get("paid_api_calls")!=0):
        raise ValueError("real SSE original receipt identity or safety gate changed")
    pages=receipt.get("pages")
    if not isinstance(pages,list) or len(pages)!=2:
        raise ValueError("expected exactly two verified source pages")
    for page,(event,day,sha,size,effective) in zip(pages,EXPECTED):
        if (page.get("event")!=event or page.get("document_date")!=day
            or page.get("sha256")!=sha or page.get("bytes")!=size
            or page.get("effective_delist_date")!=effective
            or page.get("url")!=(
                "https://www.sse.com.cn/disclosure/announcement/listing/stock/c/"
                + ("c_20260522_10819392.shtml" if effective is None else "c_20260622_10823158.shtml"))):
            raise ValueError("SSE official event hash/date/URL has changed")
    q=audit_coverage(["sh.600421"],DAYS,[])
    q.update({
        "status":"TWO_OFFICIAL_SSE_EVENT_PAGES_OBSERVED_PIT_COVERAGE_MISSING",
        "official_host_pages_observed":2,
        "official_pages_sha256":[p["sha256"] for p in pages],
        "official_announcement_effective_delist_date":"2026-06-26",
        "effective_date_as_historical_tradability_certification":False,
        "official_intraday_publication_instant_verified":False,
        "original_sse_html_durably_replayable":False,
        "scope_is_full_mainboard":False,
        "trade_gate":"BLOCKED",
        "orders":[],
        "executable_candidates":[],
    })
    return q

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--receipt",default="reports/p3_sse_two_official_original_sha_observed_20261022.json")
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    result=reconcile(json.loads(Path(args.receipt).read_text("utf-8")))
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"coverage":f'{result["verified_evidence_cells"]}/{result["required_evidence_cells"]}',"trade_gate":result["trade_gate"]}))

if __name__=="__main__":
    main()
