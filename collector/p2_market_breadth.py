"""Equal-weight vendor universe breadth, not a macro index or historical PIT universe."""
import argparse,json
from decimal import Decimal as D
from pathlib import Path

def evaluate(source):
    if source["trade_gate"]!="BLOCKED" or source["orders"]!=[] or source["executable_candidates"]!=[] or source["historical_PIT_verified"] is not False:raise ValueError("unsafe input")
    codes=source["universe"]
    if len(codes)!=3194 or len(set(codes))!=3194:raise ValueError("wrong universe")
    rows=source["returns"];by={r["code"]:r for r in rows}
    if len(rows)!=3194 or set(by)!=set(codes):raise ValueError("incomplete returns")
    values=[]
    for r in rows:
        if r["asof"]!=source["asof"]:raise ValueError("cutoff mismatch")
        if r["window_verified"] is not True:continue
        x=D(str(r["return20_pct"]))
        if not x.is_finite() or x<=-100:raise ValueError("invalid return")
        values.append(x)
    n=len(values);up=sum(x>0 for x in values);down=sum(x<0 for x in values)
    coverage=D(n)/len(codes);breadth=D(up)/n if n else D(0)
    mean=sum(values)/n if n else None
    # Predefined diagnostic, not optimized or used for deployment.
    state="INSUFFICIENT_COVERAGE" if coverage<D(".98") else "BROAD_STRENGTH" if breadth>=D(".6") and mean>0 else "BROAD_WEAKNESS" if breadth<=D(".4") and mean<0 else "MIXED"
    return dict(asof=source["asof"],universe_issuers=len(codes),valid_returns=n,missing_returns=len(codes)-n,positive=up,negative=down,flat=n-up-down,coverage_pct=str((coverage*100).quantize(D(".0001"))),positive_breadth_pct=str((breadth*100).quantize(D(".0001"))) if n else None,mean_return20_pct=str(mean.quantize(D(".0001"))) if mean is not None else None,research_state=state,thresholds={"min_coverage":"0.98","positive_breadth":"0.6","negative_breadth":"0.4"},official_index_verified=False,macro_verified=False,corporate_actions_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=evaluate(json.loads(a.input.read_bytes()));a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_MARKET_BREADTH:",json.dumps(r))
