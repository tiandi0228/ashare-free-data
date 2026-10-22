"""Independent 128-issuer-day point-in-time coverage denominator from replayed CSVs.

Vendor OHLC observation never qualifies as independently authenticated
historical listing/ST/halt/delist state. No synthetic rows are made.
"""
import argparse,csv,json,hashlib
from collections import Counter
from pathlib import Path
from collector.p1_128_source_replay_audit import audit

MANIFEST_SHA="f70bbb790e33dfda2354efad6433a92f6d64f768a5af80e66d8a7db62008bfdf"

def coverage(root):
    root=Path(root)
    checked=audit(root,expected_manifest_sha=MANIFEST_SHA)
    state_counts=Counter()
    securities=set()
    issuer_sessions=set()
    seen_files=0
    for receipt in root.rglob("quality.json"):
        q=json.loads(receipt.read_text())
        for e in q["issuer_receipts"]:
            code=e["code"]
            securities.add(code)
            file=receipt.parent/(code.replace(".","_")+".csv")
            raw=file.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=e["sha256"]:
                raise ValueError("source digest no longer matches")
            rows=list(csv.DictReader(raw.decode("utf-8").splitlines()))
            if len(rows)!=e["rows"]:
                raise ValueError("source row count changed")
            for r in rows:
                k=(code,r["date"])
                if k in issuer_sessions:
                    raise ValueError("duplicate issuer-date")
                issuer_sessions.add(k)
                state_counts[r["tradestatus"]]+=1
            seen_files+=1
    total=len(issuer_sessions)
    if (total!=checked["historical_rows"] or len(securities)!=128 or
        seen_files!=128 or set(state_counts)!={"0","1"} or
        state_counts["1"]!=checked["active_status_rows"] or
        state_counts["0"]!=checked["suspended_status_rows"]):
        raise ValueError("independent daily-coverage reconciliation failed")
    # Each source row needs separately authenticated PIT universe + risk status
    # before it can contribute to the eligible research/backtest denominator.
    return {"phase":"P3_STRATIFIED_REAL_ISSUER_DAY_PIT_COVERAGE",
            "manifest_sha256":MANIFEST_SHA,
            "source_issuer_count":128,"source_issuer_days":total,
            "vendor_active_rows_unverified":state_counts["1"],
            "vendor_suspended_rows_unverified":state_counts["0"],
            "peer_missing_dates_not_trading_rows":checked["total_peer_missing_issuer_days"],
            "official_PIT_listing_certified_issuer_days":0,
            "official_PIT_ST_halt_delist_certified_issuer_days":0,
            "complete_PIT_trade_eligible_issuer_days":0,
            "complete_PIT_trade_eligible_coverage_pct":0.0,
            "no_official_history_does_not_mean_no_risk":True,
            "full_market_universe_verified":False,
            "historical_source_acquisition_time_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=coverage(a.input)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+chr(10))
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
