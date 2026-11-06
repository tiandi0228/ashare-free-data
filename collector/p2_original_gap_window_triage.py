"""Explain P2 insufficient 21-bar windows using SHA-verified ORIGINAL vendor CSVs.

This diagnoses *vendor* row coverage, not issuer official suspension/ST/PIT.
Never delete a gap, manufacture a missing bar, or bridge suspended observations.
"""
import argparse,csv,hashlib,json
from datetime import date
from pathlib import Path
from collector.baostock_batch import END
from collector.p2_independent_bars import assess

GAP_REASON="INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"
SOURCE_PHASE="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
def classify(rows,asof=END):
    """Check frozen 21 vendor-row trailing window; no inferred missing dates."""
    try:
        cutoff=date.fromisoformat(asof)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid as-of date") from exc
    if not isinstance(rows,list) or not rows:
        raise ValueError("missing original vendor observations")
    previous=None
    history=[]
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("invalid original vendor row")
        try:
            day=date.fromisoformat(row["date"])
        except (KeyError,TypeError,ValueError) as exc:
            raise ValueError("invalid original vendor row date") from exc
        if previous is not None and day<=previous:
            raise ValueError("duplicate or unordered original vendor dates")
        previous=day
        if row.get("tradestatus") not in ("0","1"):
            raise ValueError("unknown original vendor trade status")
        if day<=cutoff:
            history.append(row)
    if not history or history[-1]["date"]!=asof:
        raise ValueError("missing exactly as-of original vendor row")
    if history[-1]["tradestatus"]!="1":
        raise ValueError("as-of original is not tradable")
    recent=history[-21:]
    if len(recent)<21:
        reason="FEWER_THAN_21_VENDOR_ROWS_ASOF"
    elif any(r["tradestatus"]!="1" for r in recent):
        reason="VENDOR_SUSPENDED_ROW_WITHIN_LAST_21"
    else:
        raise ValueError("source rows do not explain frozen P2 gap")
    return {"diagnosis":reason,"asof_date":asof,
            "available_vendor_rows_through_asof":len(history),
            "trailing_vendor_rows":len(recent),
            "trailing_vendor_suspended_rows":sum(r["tradestatus"]=="0" for r in recent),
            "first_trailing_vendor_date":recent[0]["date"],
            "latest_original_vendor_date":history[-1]["date"],
            "official_halt_explanation_authenticated":False,
            "vendor_row_window_is_calendar_coverage":False}

def diagnose(coverage,archive_epoch):
    if (not isinstance(coverage,dict) or coverage.get("phase")!=SOURCE_PHASE
            or coverage.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
            or coverage.get("trade_gate")!="BLOCKED"
            or coverage.get("historical_PIT_verified") is not False
            or coverage.get("coverage_certified_for_trading") is not False
            or coverage.get("orders")!=[]
            or coverage.get("full_archive_evidence_accounted") is not True):
        raise ValueError("unsafe P2 source research coverage")
    codes=coverage.get("gap_issuer_codes")
    counts=coverage.get("gap_reason_counts")
    if (not isinstance(codes,list) or not codes or
            any(not isinstance(c,str) for c in codes) or
            codes!=sorted(set(codes)) or
            not isinstance(counts,dict) or counts!={GAP_REASON:len(codes)} or
            coverage.get("issuer_evidence_gap_count")!=len(codes)):
        raise ValueError("unexpected P2 gap types or damaged summary")
    epoch=coverage.get("source_epoch_sha256")
    root=Path(archive_epoch)
    if (not isinstance(epoch,str) or len(epoch)!=64 or
            root.name!=epoch[:16]):
        raise ValueError("wrong source epoch archive")
    index={}
    for p in sorted(root.glob("shard_*/quality.json")):
        receipt=json.loads(p.read_text())
        if (receipt.get("status")!="OBSERVED_SUBSET_UNVERIFIED" or
                receipt.get("trade_gate")!="BLOCKED" or
                receipt.get("historical_point_in_time_universe_verified") is not False):
            raise ValueError("unsafe original P1 receipt")
        for item in receipt.get("results",[]):
            code=item.get("code")
            if code in codes:
                if code in index:raise ValueError("duplicate gap issuer in archived originals")
                index[code]=(p.parent,item)
    if set(index)!=set(codes):
        raise ValueError("missing SHA-original for one or more P2 gaps")
    results=[]
    for code in codes:
        folder,item=index[code]
        if item.get("status")!="OBSERVED_UNVERIFIED":
            raise ValueError("incomplete original vendor record")
        file=folder/(code.replace(".","_")+".csv")
        raw=file.read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        if item.get("sha256")!=digest:
            raise ValueError("original vendor SHA mismatch")
        audited=assess(folder)
        if not audited.get("source_csv_sha_validated") or audited.get("trade_gate")!="BLOCKED":
            raise ValueError("original P1 shard audit failed")
        rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
        detail=classify(rows)
        results.append({"issuer":code,"original_csv_sha256":digest,
                        "source_shard":folder.name,**detail})
    groups={r["diagnosis"]:sum(x["diagnosis"]==r["diagnosis"] for x in results)
            for r in results}
    return {"phase":"P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS",
        "status":"SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY",
        "source_epoch_sha256":epoch,
        "asof_completed_day":END,
        "research_gap_issuers":len(results),
        "diagnosis_counts":groups,
        "results":results,
        "coverage_gaps_resolved":0,
        "historical_halt_intervals_certified":0,
        "historical_ST_states_certified":0,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"buy_signals":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--coverage",required=True,type=Path)
    p.add_argument("--archive-epoch",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    report=diagnose(json.loads(a.coverage.read_text()),a.archive_epoch)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":report["status"],
        "research_gap_issuers":report["research_gap_issuers"],
        "diagnosis_counts":report["diagnosis_counts"],
        "coverage_gaps_resolved":0,"trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
