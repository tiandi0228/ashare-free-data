"""Reconcile frozen vendor peer-session gaps with a first-party SSE IPO listing notice."""
import argparse,json
from datetime import date
from pathlib import Path

OFFICIAL={"issuer":"sh.603014","listing_date":"2025-05-19",
          "notice_date":"2025-05-16",
          "publisher":"Shanghai Stock Exchange",
          "url":"https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/c_20250516_10779082.shtml",
          "source_type":"OFFICIAL_EXCHANGE_LISTING_NOTICE_OBSERVED_RETROSPECTIVELY"}
def reconcile(report):
    if (report.get("phase")!="P1_128_LIVE_CROSS_RUN_INDEPENDENT_AUDIT" or
        report.get("verified_unique_issuers")!=128 or report.get("verified_batches")!=16 or
        report.get("manifest_sha256")!="f70bbb790e33dfda2354efad6433a92f6d64f768a5af80e66d8a7db62008bfdf" or
        report.get("trade_gate")!="BLOCKED" or
        report.get("official_PIT_universe_verified") is not False):
        raise ValueError("unexpected stratified source quality audit")
    missing=report.get("missing_peer_date_details")
    if not isinstance(missing,list) or len(missing)!=report.get("total_peer_missing_issuer_days"):
        raise ValueError("missing or partial gap detail")
    ipo_day=date.fromisoformat(OFFICIAL["listing_date"])
    explained=[]
    unresolved=[]
    for item in missing:
        if (item.get("code")==OFFICIAL["issuer"] and
            item.get("position")=="BEFORE_FIRST_VENDOR_ROW" and
            date.fromisoformat(item["date"])<ipo_day and
            item.get("reason_authenticated") is False):
            explained.append(item)
        else:
            unresolved.append(item)
    return {"phase":"P1_128_EXCHANGE_IPO_GAP_RECONCILIATION",
            "total_peer_missing":len(missing),
            "prelisting_consistent_gaps":len(explained),
            "unresolved_gaps":len(unresolved),
            "official_listing_evidence":OFFICIAL,
            "independent_original_notice_bytes_verified":False,
            "historical_announcement_publication_instant_verified":False,
            "per_day_vendor_status_officially_certified":False,
            "historical_point_in_time_issuer_pool_verified":False,
            "research_only":True,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--infile",required=True);p.add_argument("--out",required=True)
    args=p.parse_args()
    result=reconcile(json.loads(Path(args.infile).read_text()))
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
