"""Four independent, read-only parallel-development acceptance contracts.

All inputs are external untrusted research evidence. Passing a structural
preflight is never a buy signal, historical PIT proof, executable quote,
certified backtest, or authorization to place orders.
"""
import argparse
import datetime as dt
import json
import re
from decimal import Decimal,InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

MAINBOARD=re.compile(r"(?:00\d{4}|60\d{4})\Z")
SHA=re.compile(r"[a-f0-9]{64}\Z")
TZ=ZoneInfo("Asia/Shanghai")
FIELDS=("trend","relative_volume","sector_strength","drawdown_risk")
PHASE="PARALLEL_FOUR_LANE_RESEARCH_CONTRACT"
def blocked(name,status,reasons,**more):
    return dict(phase=PHASE,lane=name,status=status,reasons=reasons,
                trade_gate="BLOCKED",orders=[],executable_candidates=[],
                actionable_buy_signals=[],certified=False,**more)

def number(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)):
        raise ValueError("numeric strings or ints required")
    try:x=Decimal(str(value))
    except InvalidOperation as e:raise ValueError("invalid numeric") from e
    if not x.is_finite():raise ValueError("nonfinite numeric")
    return x

def stamp(value):
    if not isinstance(value,str):raise ValueError("timestamp absent")
    t=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError("naive time")
    return t.astimezone(TZ)

def rank_universe(payload):
    """Freeze an all-industry scoring recipe, but never claim a sampled input is full universe."""
    name="MAINBOARD_UNIVERSE_RESEARCH_RANKING"
    if not isinstance(payload,dict) or not isinstance(payload.get("rows"),list):
        return blocked(name,"REJECTED",["NO_RESEARCH_UNIVERSE"])
    rows=payload["rows"]
    if not 1<=len(rows)<=5000:return blocked(name,"REJECTED",["EMPTY_OR_UNBOUNDED_UNIVERSE"])
    ranked=[];seen=set()
    for i,row in enumerate(rows):
        try:
            if not isinstance(row,dict):raise ValueError()
            code=row["code"]
            if not isinstance(code,str) or not MAINBOARD.fullmatch(code) or code in seen:raise ValueError()
            seen.add(code)
            if row.get("is_st") is not False or row.get("halted") is not False:raise ValueError()
            sector=row["sector"]
            if not isinstance(sector,str) or not 1<=len(sector)<=64:raise ValueError()
            vals={k:number(row[k]) for k in FIELDS}
            if not(all(Decimal("0")<=v<=Decimal("100") for v in vals.values())):raise ValueError()
            # Score recipe is fixed, not tuned to outcomes, and no price targets are invented.
            score=(vals["trend"]*Decimal("0.30")+
                   vals["relative_volume"]*Decimal("0.25")+
                   vals["sector_strength"]*Decimal("0.30")-
                   vals["drawdown_risk"]*Decimal("0.15"))
            ranked.append({"code":code,"sector":sector,"research_score":str(score.quantize(Decimal("0.01")))})
        except (KeyError,TypeError,ValueError,InvalidOperation):
            return blocked(name,"REJECTED",[f"ROW_{i}_UNVERIFIABLE"])
    ranked.sort(key=lambda r:(-Decimal(r["research_score"]),r["code"]))
    return blocked(name,"RESEARCH_RANKING_NOT_ACTIONABLE",
                   ["HISTORICAL_PIT_NOT_AUTHENTICATED","UNIVERSE_COVERAGE_NOT_CERTIFIED",
                    "SCORE_NOT_OUT_OF_SAMPLE_VALIDATED","QUOTE_EXECUTION_NOT_VERIFIED"],
                   rows_inspected=len(ranked),research_ranking=ranked[:50],
                   ranking_formula="0.30 trend + 0.25 relative_volume + 0.30 sector_strength - 0.15 drawdown_risk")

def align_quotes(payload):
    """Two independent *quote* sources, not minute-close, compared at a declared clock."""
    name="TWO_SOURCE_QUOTE_TIME_ALIGNMENT"
    try:
        if not isinstance(payload,dict):raise ValueError()
        now=stamp(payload["checked_at"])
        a,b=payload["quotes"]
        if not isinstance(a,dict) or not isinstance(b,dict):raise ValueError()
        if a.get("source")==b.get("source") or not all(
            isinstance(x.get("source"),str) and x["source"] for x in (a,b)):raise ValueError()
        if a.get("code")!=b.get("code") or not MAINBOARD.fullmatch(a.get("code","")):raise ValueError()
        t1,t2=stamp(a["quote_time"]),stamp(b["quote_time"])
        p1,p2=number(a["price"]),number(b["price"])
        if p1<=0 or p2<=0 or not(now.date()==t1.date()==t2.date()):raise ValueError()
        # 15s max age, future tolerance 2s; independent time skew <= 3s.
        ages=[(now-t).total_seconds() for t in (t1,t2)]
        skew=abs((t1-t2).total_seconds())
        if not all(-2<=age<=15 for age in ages):
            return blocked(name,"REJECTED",["QUOTE_STALE_OR_FUTURE"])
        if skew>3:return blocked(name,"REJECTED",["SOURCE_TIMESTAMPS_NOT_ALIGNED"])
        diff=abs(p1-p2)
        if diff>Decimal("0.01"):
            return blocked(name,"REJECTED",["SOURCE_PRICES_DISAGREE"],difference_cny=str(diff))
        return blocked(name,"TIME_ALIGNED_QUOTE_CANDIDATE_NOT_CERTIFIED",
                       ["SOURCE_INDEPENDENCE_NOT_ATTESTED",
                        "EXCHANGE_BEST_BID_ASK_AND_SESSION_NOT_CERTIFIED",
                        "GITHUB_CRON_NOT_15_SECOND_LIVE_FEED"],
                       quote_time_skew_seconds=skew,
                       difference_cny=str(diff),quote_freshness_structural_check=True)
    except (KeyError,ValueError,TypeError,InvalidOperation):
        return blocked(name,"REJECTED",["UNVERIFIABLE_QUOTE_EVIDENCE"])

def pit_facts(payload):
    name="PIT_STATUS_AND_DISCLOSURE_COVERAGE"
    if not isinstance(payload,dict) or not isinstance(payload.get("facts"),list):
        return blocked(name,"REJECTED",["MISSING_PIT_FACTS"])
    facts=payload["facts"]
    if not 1<=len(facts)<=2000:return blocked(name,"REJECTED",["MISSING_OR_UNBOUNDED_PIT_FACTS"])
    try:
        at=stamp(payload["decision_at"])
        required={"listing","st","halt","corporate_action"}
        coverage={}
        for i,f in enumerate(facts):
            if not isinstance(f,dict) or f.get("kind") not in required:
                return blocked(name,"REJECTED",[f"FACT_{i}_INVALID_KIND"])
            code=f.get("code")
            if not isinstance(code,str) or not MAINBOARD.fullmatch(code):
                return blocked(name,"REJECTED",[f"FACT_{i}_INVALID_SYMBOL"])
            publication=stamp(f["published_at"])
            available=stamp(f["available_at"])
            effective=stamp(f["effective_from"])
            end=stamp(f["effective_to"]) if f.get("effective_to") is not None else None
            if publication>available or available>at or effective>at or (end and (end<=effective or end<=at)):
                return blocked(name,"REJECTED",[f"FACT_{i}_LOOKAHEAD_OR_NOT_EFFECTIVE"])
            if not isinstance(f.get("original_sha256"),str) or not SHA.fullmatch(f["original_sha256"]):
                return blocked(name,"REJECTED",[f"FACT_{i}_SOURCE_DIGEST_MISSING"])
            if f.get("original_durably_archived") is not True:
                return blocked(name,"REJECTED",[f"FACT_{i}_ORIGINAL_NOT_ARCHIVED"])
            key=(code,f["kind"])
            if key in coverage:return blocked(name,"REJECTED",[f"FACT_{i}_DUPLICATE"])
            coverage[key]=True
        codes={x[0] for x in coverage}
        gaps={code:sorted(required-{kind for c,kind in coverage if c==code}) for code in sorted(codes)}
        if any(gaps.values()):
            return blocked(name,"REJECTED",["MISSING_ASOF_SECURITY_FACT_KINDS"],coverage_gaps=gaps)
        return blocked(name,"STRUCTURAL_PIT_COVERAGE_NOT_AUTHENTICATED",
                       ["ORIGINAL_SOURCE_PUBLICATION_NOT_INDEPENDENTLY_REPLAYED",
                        "FULL_HISTORICAL_UNIVERSE_AND_COMPANY_ACTIONS_NOT_CERTIFIED"],
                       covered_symbols=len(codes),facts_checked=len(facts))
    except (KeyError,ValueError,TypeError,InvalidOperation):
        return blocked(name,"REJECTED",["UNVERIFIABLE_PIT_TIMESTAMPS"])

def audit_forward(payload):
    """Require frozen signal instant and independently dated later observations."""
    name="FORWARD_SIMULATION_AND_REVIEW_CONTRACT"
    if not isinstance(payload,dict) or not isinstance(payload.get("records"),list):
        return blocked(name,"REJECTED",["MISSING_FORWARD_RECORDS"])
    rows=payload["records"]
    if not 1<=len(rows)<=500:return blocked(name,"REJECTED",["EMPTY_OR_UNBOUNDED_FORWARD_RECORDS"])
    ids=set()
    for i,row in enumerate(rows):
        try:
            if not isinstance(row,dict) or not isinstance(row.get("id"),str) or row["id"] in ids:raise ValueError()
            ids.add(row["id"])
            decision=stamp(row["decision_at"])
            observed=stamp(row["observed_at"])
            frozen=stamp(row["frozen_at"])
            if frozen>decision or observed<=decision:raise ValueError()
            if row.get("outcome") not in ("NO_FILL","CANCELLED","OPEN","CLOSED","UNKNOWN"):raise ValueError()
            if row.get("trade_gate")!="BLOCKED" or row.get("orders")!=[]:raise ValueError()
            if row.get("original_signal_sha256") is None or not SHA.fullmatch(row["original_signal_sha256"]):raise ValueError()
        except (KeyError,TypeError,ValueError,InvalidOperation):
            return blocked(name,"REJECTED",[f"ROW_{i}_FORWARD_EVIDENCE_INVALID"])
    return blocked(name,"FORWARD_OBSERVATION_STRUCTURE_ONLY",
                   ["OUTCOMES_NOT_INDEPENDENTLY_ATTESTED",
                    "NO_BROKER_EXECUTION_OR_EXCHANGE_FILL_AUTHENTICATION",
                    "NO_OOS_STRATEGY_APPROVAL"],
                   observed_records=len(rows),outcome_counts={
                       state:sum(x["outcome"]==state for x in rows)
                       for state in ("NO_FILL","CANCELLED","OPEN","CLOSED","UNKNOWN")})

LANES={"ranking":rank_universe,"quotes":align_quotes,
       "pit":pit_facts,"forward":audit_forward}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--lane",required=True,choices=sorted(LANES))
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    try:r=LANES[args.lane](json.loads(Path(args.input).read_text()))
    except (OSError,ValueError,UnicodeError):
        r=LANES[args.lane](None)
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"lane":args.lane,"status":r["status"],"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
