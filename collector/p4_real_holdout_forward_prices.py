"""Strictly chronological, observed MA20-event price outcomes from real archives.

Forward percentage is signal-close to third later vendor-close, NOT strategy
return: signal only exists after the first close, cannot transact at that price.
Every source SHA, event and following original row is independently replayed.
No fees, fills, OOS alpha certification, portfolio PnL, or buy orders.
"""
import argparse,csv,hashlib,json,re
from datetime import date
from decimal import Decimal,InvalidOperation,ROUND_HALF_EVEN
from pathlib import Path
from collector.p4_independent_event_evidence import verify

SHA=re.compile(r"[a-f0-9]{40}\Z")
PHASE="P4_REAL_HOLDOUT_FORWARD_PRICE_OBSERVATIONS"
Q=Decimal("0.0001")

def observe(root,manifest):
    base={"phase":PHASE,"status":"REJECTED",
          "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
          "actionable_buy_signals":[],"fills_assumed":0,
          "strategy_backtest_certified":False,"historical_OOS_validated":False,
          "historical_PIT_verified":False,"returns_computed_as_trades":False}
    def fail(reason):return dict(base,reason=reason)
    try:
        folder=Path(root)
        data=json.loads(Path(manifest).read_text())
        pinned=data.get("archive_commit_sha")
        if not isinstance(pinned,str) or not SHA.fullmatch(pinned):
            return fail("MISSING_PINNED_ARCHIVE_COMMIT")
        original=verify(folder,manifest)
        if original.get("trade_gate")!="BLOCKED" or original.get("orders")!=[]:
            return fail("UNSAFE_INDEPENDENT_EVENT_REPLAY")
        cutoff=date.fromisoformat(data["cutoff_inclusive"])
        events=data["nonoverlapping_event_evidence"]
        sources={}
        for path in sorted(folder.glob("*/shard_*/quality.json")):
            receipt=json.loads(path.read_text())
            for item in receipt["results"]:
                code=item["code"]
                raw=(path.parent/(code.replace(".","_")+".csv")).read_bytes()
                digest=hashlib.sha256(raw).hexdigest()
                if digest!=item["sha256"]:return fail("ORIGINAL_CSV_DIGEST_CHANGED")
                if code in sources:
                    if sources[code][0]!=digest:return fail("CONFLICTING_ISSUER_ORIGINALS")
                    continue
                sources[code]=(digest,list(csv.DictReader(raw.decode("utf-8-sig").splitlines())))
        observed=[];censored=0;blocked_vendor=0;positive=zero=negative=0
        for event in events:
            code=event["issuer"]
            digest,rows=sources[code]
            if digest!=event["source_csv_sha256"]:
                return fail("EVENT_SOURCE_MISMATCH")
            day=event["signal_completed_date"]
            if date.fromisoformat(day)<=cutoff:return fail("TRAIN_PERIOD_LEAKAGE")
            matches=[i for i,row in enumerate(rows) if row["date"]==day]
            if len(matches)!=1:return fail("SIGNAL_DATE_NOT_UNIQUE")
            index=matches[0]
            future=rows[index+1:index+4]
            if len(future)<3:
                censored+=1
                continue
            if any(r["tradestatus"]!="1" for r in future):
                blocked_vendor+=1
                continue
            try:
                start=Decimal(rows[index]["close"])
                last=Decimal(future[-1]["close"])
                if start<=0 or last<=0 or not start.is_finite() or not last.is_finite():
                    return fail("INVALID_OBSERVED_CLOSE")
                pct=(last/start-1)*100
                rounded=pct.quantize(Q,rounding=ROUND_HALF_EVEN)
            except (InvalidOperation,ValueError,ArithmeticError):
                return fail("INVALID_OBSERVED_CLOSE")
            positive+=pct>0;negative+=pct<0;zero+=pct==0
            observed.append({
                "issuer":code,"signal_close_day":day,"source_csv_sha256":digest,
                "signal_known_after_close_only":True,
                "observed_third_later_vendor_day":future[2]["date"],
                "observed_signal_close":str(start),
                "observed_third_later_close":str(last),
                "close_to_third_later_close_change_pct":str(rounded),
                "execution_at_signal_close_assumed":False,
                "entry_filled":False,"trade_return":None,
            })
        total=len(events)
        if len(observed)+censored+blocked_vendor!=total:
            return fail("FORWARD_EVENT_ACCOUNTING_MISMATCH")
        return dict(base,status="HOLDOUT_PRICE_OBSERVATIONS_NOT_BACKTEST",
                    archive_commit_sha=pinned,holdout_cutoff_inclusive=cutoff.isoformat(),
                    verified_ma20_crossing_events=total,
                    observed_with_three_vendor_tradable_rows=len(observed),
                    censored_insufficient_following_rows=censored,
                    unscorable_future_vendor_status=blocked_vendor,
                    observed_positive_close_changes=positive,
                    observed_zero_close_changes=zero,
                    observed_negative_close_changes=negative,
                    research_observations=observed,
                    signal_close_execution_possible_proven=False,
                    sector_selection_or_pit_coverage_verified=False,
                    limitations=[
                       "SIGNAL_CLOSE_IS_NOT_EXECUTABLE_AFTER_CLOSE",
                       "FOLLOWING_VENDOR_CLOSE_NOT_T_PLUS_ONE_EXIT_FILL",
                       "NOT_ADJUSTED_FOR_FEES_SLIPPAGE_OR_BID_ASK",
                       "RETROSPECTIVE_VENDOR_UNIVERSE_NOT_HISTORICAL_PIT",
                       "CENSORED_AND_SUSPENDED_EVENTS_NOT_ZERO_RETURNS",
                       "NO_INDEPENDENT_OOS_STRATEGY_OR_PORTFOLIO_APPROVAL",
                    ])
    except (OSError,ValueError,KeyError,TypeError,IndexError,InvalidOperation):
        return fail("SOURCE_OR_EVENT_EVIDENCE_UNVERIFIABLE")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--manifest",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=observe(args.root,args.manifest)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result.get(k) for k in (
       "status","verified_ma20_crossing_events",
       "observed_with_three_vendor_tradable_rows",
       "censored_insufficient_following_rows",
       "unscorable_future_vendor_status","trade_gate")}))
    if result["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
