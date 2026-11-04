"""Fail-closed directional and selection-bias report on *observed prices*.

The input is the independently verified real vendor-price P4 manifest.
This module audits its accounting but is not a trading backtest, OOS
certification, signal model approval, or historical PIT evidence.
"""
import argparse,json,re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
PHASE="P4_HOLDOUT_DIRECTION_AND_CENSORSHIP_AUDIT"
COMMIT=re.compile(r"[0-9a-f]{40}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
Q=Decimal("0.0001")
def audit(payload):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "strategy_backtest_certified":False,"historical_OOS_validated":False,
          "historical_PIT_verified":False,"fills_assumed":0,
          "win_rate_claimed":False,"trade_returns_calculated":False}
    def reject(reason):return dict(base,reason=reason)
    try:
        if not isinstance(payload,dict) or payload.get("status")!="HOLDOUT_PRICE_OBSERVATIONS_NOT_BACKTEST" or (
            payload.get("phase")!="P4_REAL_HOLDOUT_FORWARD_PRICE_OBSERVATIONS"
            or payload.get("trade_gate")!="BLOCKED" or payload.get("orders")!=[]
            or payload.get("executable_candidates")!=[]
            or payload.get("actionable_buy_signals")!=[]
            or payload.get("strategy_backtest_certified") is not False
            or payload.get("historical_OOS_validated") is not False
            or payload.get("historical_PIT_verified") is not False
            or payload.get("returns_computed_as_trades") is not False
            or payload.get("fills_assumed")!=0
            or not isinstance(payload.get("archive_commit_sha"),str)
            or not COMMIT.fullmatch(payload["archive_commit_sha"])):
            return reject("UNSAFE_OR_UNPINNED_SOURCE")
        def count(field):
            n=payload[field]
            if type(n) is not int or n<0:raise ValueError(field)
            return n
        total=count("verified_ma20_crossing_events")
        mature=count("observed_with_three_vendor_tradable_rows")
        censored=count("censored_insufficient_following_rows")
        blocked=count("unscorable_future_vendor_status")
        positive=count("observed_positive_close_changes")
        negative=count("observed_negative_close_changes")
        zero=count("observed_zero_close_changes")
        if total!=mature+censored+blocked or mature!=positive+negative+zero:
            return reject("EVENT_OUTCOME_COUNTERS_INCONSISTENT")
        rows=payload.get("research_observations")
        if not isinstance(rows,list) or len(rows)!=mature or len(rows)>50000:
            return reject("INVALID_OR_TRUNCATED_EVENT_EVIDENCE")
        cutoff=date.fromisoformat(payload["holdout_cutoff_inclusive"])
        observed=Counter();issuer=Counter();monthly=Counter()
        seen=set()
        exact_positive=exact_negative=exact_zero=0
        for i,item in enumerate(rows):
            if not isinstance(item,dict):return reject(f"ROW_{i}_INVALID")
            code=item.get("issuer");day=item.get("signal_close_day")
            if (not isinstance(code,str) or not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",code)
                or not isinstance(day,str) or date.fromisoformat(day)<=cutoff
                or not isinstance(item.get("source_csv_sha256"),str)
                or not SHA.fullmatch(item["source_csv_sha256"])
                or item.get("signal_known_after_close_only") is not True
                or item.get("execution_at_signal_close_assumed") is not False
                or item.get("entry_filled") is not False
                or item.get("trade_return") is not None):
                return reject(f"ROW_{i}_UNSAFE_SOURCE")
            end=item.get("observed_third_later_vendor_day")
            if not isinstance(end,str) or date.fromisoformat(end)<=date.fromisoformat(day):
                return reject(f"ROW_{i}_WRONG_FORWARD_ORDER")
            key=(code,day)
            if key in seen:return reject("DUPLICATE_ISSUER_SIGNAL_DAY")
            seen.add(key)
            start=Decimal(item["observed_signal_close"])
            finish=Decimal(item["observed_third_later_close"])
            reported=Decimal(item["close_to_third_later_close_change_pct"])
            if (not all(n.is_finite() for n in (start,finish,reported)) or
                start<=0 or finish<=0):return reject(f"ROW_{i}_INVALID_PRICES")
            actual=(finish/start-1)*100
            if actual.quantize(Q,rounding=ROUND_HALF_EVEN)!=reported:
                return reject(f"ROW_{i}_PRICE_CHANGE_MISMATCH")
            direction="positive" if actual>0 else ("negative" if actual<0 else "zero")
            observed[direction]+=1
            issuer[code]+=1
            monthly[(day[:7],direction)]+=1
        if (observed["positive"],observed["negative"],observed["zero"])!=(
            positive,negative,zero):
            return reject("REPORTED_DIRECTION_COUNTERS_MISMATCH")
        def percentage(n,den):
            return str((Decimal(n)*100/Decimal(den)).quantize(Q)) if den else None
        by_month=[]
        for month in sorted({k[0] for k in monthly}):
            counts={kind:monthly[(month,kind)] for kind in ("positive","negative","zero")}
            by_month.append({"signal_month":month,"observed_events":sum(counts.values()),
                             **counts})
        sorted_issuer=sorted(issuer.items(),key=lambda x:(-x[1],x[0]))
        return dict(base,status="DIRECTIONAL_OBSERVATION_BIAS_AUDITED_NOT_STRATEGY",
            source_archive_commit_sha=payload["archive_commit_sha"],
            holdout_cutoff_inclusive=cutoff.isoformat(),
            event_total=total,observed_events=mature,
            censored_events=censored,vendor_status_blocked_events=blocked,
            observed_positive=positive,observed_negative=negative,
            observed_zero=zero,
            observed_positive_share_pct=percentage(positive,mature),
            observed_negative_share_pct=percentage(negative,mature),
            observation_availability_pct=percentage(mature,total),
            censored_or_blocked_share_pct=percentage(censored+blocked,total),
            unique_issuers=len(issuer),
            most_repeated_issuer=(sorted_issuer[0][0] if sorted_issuer else None),
            max_events_one_issuer=(sorted_issuer[0][1] if sorted_issuer else 0),
            top_issuer_event_share_pct=percentage(sorted_issuer[0][1],mature) if sorted_issuer else None,
            monthly_observation_counts=by_month,
            risk_notes=[
              "OBSERVED_POSITIVE_SHARE_IS_NOT_TRADING_WIN_RATE",
              "CENSORED_AND_VENDOR_UNTRADABLE_EVENTS_ARE_NOT_ASSIGNED_ZERO_RETURN",
              "REPEATED_ISSUER_EVENTS_NOT_INDEPENDENT",
              "SIGNAL_CLOSE_NOT_EXECUTABLE_AFTER_CLOSE",
              "UNIVERSE_SURVIVORSHIP_AND_CORPORATE_ACTION_PIT_NOT_ATTESTED",
              "NO_FEES_SPREAD_SLIPPAGE_OR_BENCHMARK_ADJUSTMENT",
            ])
    except (ValueError,TypeError,KeyError,InvalidOperation,OverflowError,ArithmeticError):
        return reject("MALFORMED_OR_INCONSISTENT_INPUT")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    try:x=json.loads(Path(a.input).read_text())
    except (OSError,UnicodeError,ValueError):x=None
    r=audit(x);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:r.get(k) for k in ("status","event_total","observed_events",
        "observed_positive","observed_negative","observed_zero",
        "observation_availability_pct","trade_gate")}))
    if r["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
