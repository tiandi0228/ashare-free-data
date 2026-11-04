"""Source-pinned *exploratory* ordering of actual archived historical features.

This is NOT a buy signal, a backtest, industry-aware ranking, point-in-time
membership proof, or a validated prediction of future 3-5 trading day returns.
The source input must come from independently verified archived CSV replay.
"""
import argparse,json,re
from decimal import Decimal,InvalidOperation,ROUND_HALF_EVEN
from pathlib import Path

PHASE="P2_REAL_ARCHIVED_RESEARCH_SCREEN"
SHA=re.compile(r"[a-f0-9]{64}\Z")
COMMIT=re.compile(r"[a-f0-9]{40}\Z")
ISSUER=re.compile(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}\Z")
Q=Decimal("0.0001")
def screen(report):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "historical_PIT_verified":False,"historical_OOS_validated":False,
          "complete_mainboard_coverage":False,"strategy_alpha_validated":False}
    def fail(reason):return dict(base,reason=reason)
    if not isinstance(report,dict):return fail("MISSING_ARCHIVED_REPLAY")
    if (report.get("phase")!="P2_PAGED_REAL_ARCHIVE_FEATURE_REPLAY"
        or report.get("status")!="PAGED_REAL_ARCHIVE_RESEARCH_ONLY"
        or report.get("trade_gate")!="BLOCKED"
        or report.get("orders")!=[]
        or report.get("executable_candidates")!=[]
        or report.get("actionable_buy_signals")!=[]
        or report.get("historical_PIT_verified") is not False
        or report.get("full_market_universe_verified") is not False
        or not isinstance(report.get("source_epoch_sha256"),str)
        or not SHA.fullmatch(report["source_epoch_sha256"])
        or not isinstance(report.get("archive_commit_sha"),str)
        or not COMMIT.fullmatch(report["archive_commit_sha"])):
        return fail("UNSAFE_OR_UNPINNED_SOURCE")
    rows=report.get("features")
    gaps=report.get("evidence_gaps")
    if (not isinstance(rows,list) or not isinstance(gaps,list)
        or len(rows)>128 or len(rows)+len(gaps)>128
        or type(report.get("scoped_verified_issuers")) is not int
        or report["scoped_verified_issuers"]!=len(rows)+len(gaps)
        or report.get("computed_feature_issuers")!=len(rows)
        or report.get("missing_feature_evidence_issuers")!=len(gaps)):
        return fail("INCOMPLETE_PAGE_COUNTS")
    identifiers=set()
    scored=[]
    def decimal(v):
        if not isinstance(v,str):raise ValueError("nonstring numeric")
        x=Decimal(v)
        if not x.is_finite():raise ValueError("nonfinite")
        return x
    for i,item in enumerate(rows):
        try:
            code=item["issuer"]
            if (not isinstance(code,str) or not ISSUER.fullmatch(code)
                or code in identifiers or item.get("buy_signal") is not False
                or item.get("asof_completed_day")!=report.get("asof_completed_day")
                or not isinstance(item.get("source_original_sha256"),str)
                or not SHA.fullmatch(item["source_original_sha256"])
                or item.get("sector") is not None
                or item.get("historical_st_and_company_actions_verified") is not False):
                raise ValueError("source not verified")
            identifiers.add(code)
            close=decimal(item["last_close_cny"])
            ma20=decimal(item["ma20_close_cny"])
            ratio=decimal(item["volume_vs_prior20_ratio"])
            drawdown=decimal(item["trailing20_close_drawdown_pct"])
            if close<=0 or ma20<=0 or ratio<0 or not 0<=drawdown<=100:
                raise ValueError("invalid features")
            if item.get("above_ma20") is not (close>ma20):
                raise ValueError("contradictory ma")
            # Frozen, deliberately simple descriptive sorting (NOT alpha).
            # Cap individual contributions so spikes cannot dominate.
            ma_pct=Decimal(100)*(close/ma20-1)
            trend=max(Decimal("-20"),min(Decimal("20"),ma_pct))
            volume=min(Decimal("3"),ratio)
            score=trend+Decimal("2")*volume-drawdown/Decimal("5")
            scored.append({
                "issuer":code,
                "asof_completed_day":item["asof_completed_day"],
                "source_original_sha256":item["source_original_sha256"],
                "last_close_cny":str(close),
                "above_ma20":item["above_ma20"],
                "volume_vs_prior20_ratio":str(ratio),
                "drawdown_pct":str(drawdown),
                "descriptive_score":str(score.quantize(Q,rounding=ROUND_HALF_EVEN)),
                "buy_signal":False})
        except (ValueError,KeyError,TypeError,InvalidOperation,ArithmeticError):
            return fail(f"FEATURE_{i}_UNVERIFIABLE")
    for i,item in enumerate(gaps):
        if (not isinstance(item,dict) or not isinstance(item.get("issuer"),str)
            or not ISSUER.fullmatch(item["issuer"]) or item["issuer"] in identifiers
            or not isinstance(item.get("reason"),str) or not item["reason"]):
            return fail(f"GAP_{i}_UNVERIFIABLE")
        identifiers.add(item["issuer"])
    scored.sort(key=lambda x:(-Decimal(x["descriptive_score"]),x["issuer"]))
    return dict(base,status="DESCRIPTIVE_ARCHIVED_SAMPLE_ONLY",
                source_epoch_sha256=report["source_epoch_sha256"],
                archive_commit_sha=report["archive_commit_sha"],
                asof_completed_day=report["asof_completed_day"],
                source_page_index=report["page_index"],
                source_selected_shards=report["selected_shards"],
                scoped_issuers=report["scoped_verified_issuers"],
                ranked_observations=len(scored),source_gap_count=len(gaps),
                descriptive_order=scored,
                formula="clamp(100*(close/MA20-1),-20,20) + 2*min(volume_ratio,3) - drawdown_pct/5",
                limitations=[
                    "ARCHIVED_VENDOR_REPLAY_NOT_ASOF_UNIVERSE_PROOF",
                    "SOURCE_PIT_ST_HALT_AND_CORPORATE_ACTIONS_NOT_CERTIFIED",
                    "INDUSTRY_AND_SECTOR_ROTATION_NOT_AVAILABLE",
                    "DESCRIPTIVE_SORT_NOT_A_PREDICTIVE_STRATEGY_OR_BACKTEST",
                    "NOT_CURRENT_EXECUTABLE_MARKET_QUOTES",
                ])
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:report=json.loads(Path(a.input).read_text())
    except (OSError,UnicodeError,ValueError):report=None
    result=screen(report)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"ranked_observations":result.get("ranked_observations",0),"trade_gate":"BLOCKED"}))
    if result["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
