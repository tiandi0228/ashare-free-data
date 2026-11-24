"""Read-only bounded official-index discovery for P2 vendor-nontradable-asof gaps.

The source is an immutable SHA-backed P2 original CSV diagnosis and durable
coverage. CNINFO index matches are search leads only; neither absence nor
PDF timestamps establishes exchange status or PIT trading eligibility.
"""
import argparse
import json
import re
from datetime import date,timedelta
from pathlib import Path
from collector.p3_real_target_index_probe import query

ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
DIAGNOSIS="VENDOR_MARKED_NOT_TRADABLE_AT_ASOF"


def targets(coverage,gaps):
    if (not isinstance(coverage,dict) or not isinstance(gaps,dict)
        or coverage.get("phase")!="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
        or coverage.get("trade_gate")!="BLOCKED"
        or coverage.get("historical_PIT_verified") is not False
        or coverage.get("observed_archived_shards")!=coverage.get("checkpoint_completed_shards")
        or coverage.get("unobserved_archived_shards")!=0
        or gaps.get("phase")!="P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS"
        or gaps.get("status")!="SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY"
        or gaps.get("trade_gate")!="BLOCKED"
        or gaps.get("historical_PIT_verified") is not False
        or gaps.get("coverage_gaps_resolved")!=0
        or gaps.get("orders")!=[] or coverage.get("orders")!=[]
        or gaps.get("source_epoch_sha256")!=coverage.get("source_epoch_sha256")):
        raise ValueError("unsafe original P2 research scope")
    epoch=coverage.get("source_epoch_sha256")
    rows=gaps.get("results")
    codes=coverage.get("gap_issuer_codes")
    if (not isinstance(epoch,str) or not SHA.fullmatch(epoch)
        or not isinstance(rows,list) or not isinstance(codes,list)
        or codes!=sorted(set(codes)) or not 1<=len(codes)<=400
        or len(rows)!=len(codes)
        or len(rows)!=gaps.get("research_gap_issuers")
        or len(codes)!=coverage.get("issuer_evidence_gap_count")):
        raise ValueError("P2 original gap issuer accounting mismatch")
    seen=set()
    selected=[]
    for row in rows:
        issuer=row.get("issuer") if isinstance(row,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or issuer in seen or issuer not in codes
            or row.get("official_halt_explanation_authenticated") is not False
            or not isinstance(row.get("original_csv_sha256"),str)
            or not SHA.fullmatch(row["original_csv_sha256"])):
            raise ValueError("invalid SHA-bound issuer original")
        seen.add(issuer)
        if row.get("diagnosis")==DIAGNOSIS:
            if (row.get("trailing_vendor_suspended_rows",0)<1
                or row.get("asof_date") is None):
                raise ValueError("vendor-marked asof diagnosis contradicts original rows")
            day=date.fromisoformat(row["asof_date"])
            selected.append({
                "issuer":issuer,"original_vendor_csv_sha256":row["original_csv_sha256"],
                "vendor_asof_date":day.isoformat(),
                "research_window_start":(day-timedelta(days=45)).isoformat(),
                "research_window_end":(day+timedelta(days=7)).isoformat(),
                "official_asof_state_authenticated":False,
            })
    if seen!=set(codes):
        raise ValueError("P2 diagnosis omits gap issuer")
    if (len(selected)!=coverage.get("gap_reason_counts",{}).get(
            "VENDOR_NOT_TRADABLE_ASOF") or not 1<=len(selected)<=3):
        raise ValueError("asof nontradable source count mismatch")
    return sorted(selected,key=lambda r:r["issuer"])


def discover(coverage,gaps,client=query):
    chosen=targets(coverage,gaps)
    result=[]
    for row in chosen:
        issuer=row["issuer"]
        window=[row["research_window_start"],row["research_window_end"]]
        try:
            candidates=client(issuer,research_window=window)
            if not isinstance(candidates,list) or len(candidates)>90:
                raise ValueError("invalid official index response")
            for c in candidates:
                if (not isinstance(c,dict) or
                    c.get("historical_PIT_verified") is not False or
                    c.get("original_bytes_captured") is not False):
                    raise ValueError("unsafe candidate claims original certification")
            status="INDEX_CANDIDATES_UNVERIFIED" if candidates else "NO_INDEX_MATCH_NOT_NO_RISK"
        except Exception as exc:
            candidates=[]
            status="INDEX_UNAVAILABLE_NOT_NO_RISK"
            error_type=type(exc).__name__
        item={**row,"status":status,"candidates":candidates,
              "independent_exchange_status_authenticated":False}
        if status=="INDEX_UNAVAILABLE_NOT_NO_RISK":
            item["error_type"]=error_type
        result.append(item)
    return {
        "phase":"P3_THREE_ASOF_VENDOR_GAP_OFFICIAL_INDEX_RESEARCH",
        "source_epoch_sha256":coverage["source_epoch_sha256"],
        "research_issuers":len(result),
        "index_candidates":sum(len(x["candidates"]) for x in result),
        "index_unavailable":sum(x["status"]=="INDEX_UNAVAILABLE_NOT_NO_RISK" for x in result),
        "no_index_match_not_no_risk":sum(x["status"]=="NO_INDEX_MATCH_NOT_NO_RISK" for x in result),
        "results":result,"historical_first_publication_authenticated":False,
        "independent_exchange_status_authenticated":False,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"buy_signals":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--coverage",type=Path,required=True)
    p.add_argument("--gaps",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=discover(json.loads(a.coverage.read_text()),
                    json.loads(a.gaps.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"issuers":report["research_issuers"],
        "index_candidates":report["index_candidates"],
        "index_unavailable":report["index_unavailable"],
        "trade_gate":report["trade_gate"]}))


if __name__=="__main__":
    main()
