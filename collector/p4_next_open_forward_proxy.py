"""Observed next-session OPEN to third following CLOSE, not trading PnL.

Independent complete event replay and SHA verification are prerequisites.
The first later vendor open is an observable price, not a guaranteed limit-order
fill. Exit close likewise is not a verified executable price. PIT, fees, board
limits, T+1 execution and corporate actions remain uncertified.
"""
import argparse,csv,hashlib,json,re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from collector.p4_independent_event_evidence import verify

PHASE="P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES"
COMMIT=re.compile(r"[0-9a-f]{40}\Z")
Q=Decimal("0.0001")

def observe(root,manifest):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "fills_assumed":0,"trades_assumed":0,"portfolio_pnl_computed":False,
          "historical_OOS_validated":False,"historical_PIT_verified":False,
          "strategy_backtest_certified":False}
    def reject(reason):return dict(base,reason=reason)
    try:
        root=Path(root)
        data=json.loads(Path(manifest).read_text())
        commit=data.get("archive_commit_sha")
        if not isinstance(commit,str) or not COMMIT.fullmatch(commit):
            return reject("UNPINNED_ARCHIVE")
        independent=verify(root,manifest)
        if independent.get("trade_gate")!="BLOCKED" or independent.get("orders")!=[]:
            return reject("UNSAFE_INDEPENDENT_EVENT_AUDIT")
        events=data["nonoverlapping_event_evidence"]
        cutoff=date.fromisoformat(data["cutoff_inclusive"])
        needed={e["issuer"] for e in events}
        originals={}
        for receipt in sorted(root.glob("*/shard_*/quality.json")):
            raw_receipt=json.loads(receipt.read_text())
            for item in raw_receipt["results"]:
                code=item["code"]
                if code not in needed:continue
                raw=(receipt.parent/(code.replace(".","_")+".csv")).read_bytes()
                digest=hashlib.sha256(raw).hexdigest()
                if digest!=item["sha256"]:return reject("ORIGINAL_CSV_SHA_MISMATCH")
                if code in originals:
                    if originals[code][0]!=digest:return reject("CONFLICTING_ORIGINALS")
                    continue
                originals[code]=(digest,list(csv.DictReader(raw.decode("utf-8-sig").splitlines())))
        observed=[]
        counts=Counter()
        for event in events:
            code=event["issuer"]
            if code not in originals:return reject("MISSING_EVENT_ORIGINAL")
            digest,rows=originals[code]
            if digest!=event["source_csv_sha256"]:return reject("EVENT_SHA_MISMATCH")
            day=event["signal_completed_date"]
            if date.fromisoformat(day)<=cutoff:return reject("SIGNAL_LEAKED_TRAIN_PERIOD")
            indexes=[i for i,r in enumerate(rows) if r["date"]==day]
            if len(indexes)!=1:return reject("AMBIGUOUS_EVENT_DATE")
            i=indexes[0]
            future=rows[i+1:i+4]
            if len(future)<3:
                counts["censored"]+=1
                continue
            if any(r["tradestatus"]!="1" for r in future):
                counts["status_blocked"]+=1
                continue
            try:
                signal_close=Decimal(rows[i]["close"])
                next_open=Decimal(future[0]["open"])
                third_close=Decimal(future[2]["close"])
                if not all(v.is_finite() and v>0 for v in
                           (signal_close,next_open,third_close)):
                    return reject("INVALID_FORWARD_OHLC")
                gap=(next_open/signal_close-1)*100
                delta=(third_close/next_open-1)*100
            except (InvalidOperation,ValueError,ArithmeticError):
                return reject("INVALID_FORWARD_OHLC")
            counts["observed"]+=1
            counts["positive"]+=int(delta>0)
            counts["negative"]+=int(delta<0)
            counts["flat"]+=int(delta==0)
            counts["gap_up"]+=int(gap>0)
            counts["gap_down"]+=int(gap<0)
            observed.append({
                "issuer":code,
                "original_csv_sha256":digest,
                "signal_known_after_close_date":day,
                "next_vendor_date":future[0]["date"],
                "third_vendor_date":future[2]["date"],
                "signal_close":str(signal_close),
                "next_vendor_open":str(next_open),
                "third_vendor_close":str(third_close),
                "overnight_open_gap_pct":str(gap.quantize(Q,rounding=ROUND_HALF_EVEN)),
                "next_open_to_third_close_change_pct":str(delta.quantize(Q,rounding=ROUND_HALF_EVEN)),
                "next_open_fill_assumed":False,
                "exit_close_fill_assumed":False,
                "trade_return":None,
                "T_plus_1_execution_verified":False,
            })
        total=len(events)
        if counts["observed"]+counts["censored"]+counts["status_blocked"]!=total:
            return reject("EVENT_ACCOUNTING_MISMATCH")
        def pct(n,den):
            return str((Decimal(n)*100/Decimal(den)).quantize(Q)) if den else None
        return dict(base,status="OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST",
                    archive_commit_sha=commit,holdout_cutoff_inclusive=cutoff.isoformat(),
                    verified_nonoverlap_events=total,
                    observed_next_open_to_third_close=counts["observed"],
                    censored_events=counts["censored"],
                    future_vendor_status_blocked=counts["status_blocked"],
                    positive_price_changes=counts["positive"],
                    negative_price_changes=counts["negative"],
                    flat_price_changes=counts["flat"],
                    observed_overnight_gap_ups=counts["gap_up"],
                    observed_overnight_gap_downs=counts["gap_down"],
                    positive_observation_share_pct=pct(counts["positive"],counts["observed"]),
                    observation_availability_pct=pct(counts["observed"],total),
                    observed_price_pairs=observed,
                    warnings=[
                        "NEXT_VENDOR_OPEN_IS_NOT_AN_EXECUTION_PROOF",
                        "THIRD_VENDOR_CLOSE_IS_NOT_AN_EXIT_EXECUTION_PROOF",
                        "T_PLUS_ONE_AND_LIMIT_PRICE_FILLABILITY_NOT_REPLAYED",
                        "NO_LOT_SIZE_FEES_SPREAD_OR_SLIPPAGE",
                        "SOURCE_PIT_AND_POINT_IN_TIME_MAINBOARD_STATUS_NOT_ATTESTED",
                        "NOT_A_WIN_RATE_OR_VALIDATED_BACKTEST",
                    ])
    except (OSError,ValueError,TypeError,KeyError,IndexError,InvalidOperation):
        return reject("SOURCE_OR_EVENT_DATA_UNVERIFIABLE")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=observe(a.root,a.manifest)
    destination=Path(a.out);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result.get(k) for k in (
        "status","verified_nonoverlap_events","observed_next_open_to_third_close",
        "positive_price_changes","negative_price_changes","censored_events",
        "future_vendor_status_blocked","trade_gate")}))
    if result["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
