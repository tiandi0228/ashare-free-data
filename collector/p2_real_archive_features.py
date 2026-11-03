"""Real P2 archived-original daily bars -> deterministic as-of research features.

Source SHA and CSV rows are replay-checked using p2_independent_bars.assess.
No historical ST, original publication instant, sector, or complete-universe
PIT authentication. Not a market-wide scan or buy recommendation.
"""
import argparse,csv,hashlib,json,re
from datetime import date
from decimal import Decimal,InvalidOperation
from pathlib import Path
from collector.p2_independent_bars import assess

PHASE="P2_REAL_VENDOR_ARCHIVE_FEATURE_OBSERVATION"
LIMIT=128
def observe(root,asof,max_issuers=LIMIT):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "full_market_universe_verified":False,"historical_PIT_verified":False,
          "sector_classification_verified":False,"strategy_effectiveness_verified":False}
    def fail(reason):return dict(base,reason=reason)
    try:
        cutoff=date.fromisoformat(asof)
        if cutoff.isoformat()!=asof or type(max_issuers) is not int or not 1<=max_issuers<=LIMIT:
            return fail("INVALID_ASOF_OR_LIMIT")
        files=sorted(Path(root).glob("*/shard_*/quality.json"))
        if not files:return fail("NO_ORIGINAL_P2_RECEIPTS")
        if len(files)>400:return fail("UNBOUNDED_RECEIPT_INPUT")
        seen={}
        features=[]
        gaps=[]
        for p in files:
            audit=assess(p.parent)
            if audit.get("trade_gate")!="BLOCKED" or audit.get("historical_PIT_verified") is not False:
                return fail("UNSAFE_ARCHIVE_AUDIT")
            for detail in audit["details"]:
                code=detail["code"]
                if not re.fullmatch(r"(?:sh\.60\d{4}|sz\.00\d{4})",code):
                    continue
                raw=(p.parent/(code.replace(".","_")+".csv")).read_bytes()
                digest=hashlib.sha256(raw).hexdigest()
                if code in seen:
                    if seen[code]!=digest:return fail("CONFLICTING_DUPLICATE_ORIGINALS")
                    continue
                seen[code]=digest
                if len(seen)>max_issuers:return fail("SCOPE_LIMIT_REACHED_REFUSE_PARTIAL")
                rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
                history=[r for r in rows if r["date"]<=asof]
                if not history or history[-1]["date"]!=asof:
                    gaps.append({"issuer":code,"reason":"MISSING_EXACT_ASOF_CLOSE"})
                    continue
                if history[-1]["tradestatus"]!="1":
                    gaps.append({"issuer":code,"reason":"VENDOR_NOT_TRADABLE_ASOF"})
                    continue
                # Require 21 consecutive vendor-tradable observations ending
                # at as-of, so suspension won't silently bridge the window.
                recent=history[-21:]
                if len(recent)!=21 or any(r["tradestatus"]!="1" for r in recent):
                    gaps.append({"issuer":code,"reason":"INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"})
                    continue
                close=[Decimal(r["close"]) for r in recent]
                volume=[Decimal(r["volume"]) for r in recent]
                if min(close)<=0 or min(volume)<0:raise ValueError("bad vendor values")
                prior_vol=sum(volume[:-1])/Decimal(20)
                if prior_vol<=0:
                    gaps.append({"issuer":code,"reason":"PRIOR_VOLUME_UNAVAILABLE"})
                    continue
                ma20=sum(close[-20:])/Decimal(20)
                # These are reproducible observations, not validated
                # predictive scores nor risk forecasts.
                high=max(close[-20:])
                drawdown=(high-close[-1])/high*100
                features.append({
                    "issuer":code,"asof_completed_day":asof,
                    "source_original_sha256":digest,
                    "ma20_close_cny":str(ma20.quantize(Decimal("0.0001"))),
                    "last_close_cny":str(close[-1]),
                    "above_ma20":close[-1]>ma20,
                    "volume_vs_prior20_ratio":str((volume[-1]/prior_vol).quantize(Decimal("0.0001"))),
                    "trailing20_close_drawdown_pct":str(drawdown.quantize(Decimal("0.0001"))),
                    "sector":None,
                    "historical_st_and_company_actions_verified":False,
                    "buy_signal":False,
                })
        return dict(base,status="REAL_ARCHIVED_BAR_FEATURES_RESEARCH_ONLY",
                    asof_completed_day=asof,
                    scoped_verified_issuers=len(seen),
                    feature_issuers=len(features),
                    insufficient_evidence_issuers=len(gaps),
                    features=features,evidence_gaps=gaps,
                    reasons=[
                        "FULL_HISTORICAL_MAINBOARD_COVERAGE_NOT_VERIFIED",
                        "RETROSPECTIVE_VENDOR_BARS_NOT_HISTORICAL_PIT_PROOF",
                        "NO_INDEPENDENT_SECTOR_METADATA_OR_CROSS_SECTIONAL_SIGNAL",
                        "NO_FORWARD_STRATEGY_VALIDATION_OR_EXECUTABLE_QUOTES",
                    ])
    except (OSError,ValueError,TypeError,KeyError,InvalidOperation,ArithmeticError):
        return fail("ARCHIVE_READ_OR_INTEGRITY_FAILURE")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--asof",required=True)
    p.add_argument("--max-issuers",type=int,default=LIMIT)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=observe(a.root,a.asof,a.max_issuers)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],
                      "feature_issuers":result.get("feature_issuers",0),
                      "trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
