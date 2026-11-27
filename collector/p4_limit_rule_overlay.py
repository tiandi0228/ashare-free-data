"""Transcribed official rule version overlay; security-specific limits remain unverified."""
import argparse,json
from datetime import date
from collections import Counter
from pathlib import Path
EFFECTIVE=date(2026,7,6)
SOURCES={"SSE":"https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml","SZSE":"https://www.szse.cn/lawrules/rule/trade/current/t20260424_620190.html","SSE_CHANGE":"https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml","SZSE_GUIDE":"https://www.szse.cn/lawrules/service/member/t20260630_621404.html"}
def classify(day,bands):
    d=date.fromisoformat(day)
    if not date(2026,1,1)<=d<=date(2026,11,25):raise ValueError("unsupported date")
    allowed={"10.00"} if d>=EFFECTIVE else {"5.00","10.00"}
    if not set(bands)<={"5.00","10.00"}:raise ValueError("unknown hypothesis")
    return "GENERAL_RULE_COMPATIBLE_NOT_CERTIFIED" if set(bands)&allowed else "GENERAL_RULE_MISMATCH_REQUIRES_REFERENCE_PRICE_REVIEW"
def run(risk):
    if risk["trade_gate"]!="BLOCKED" or risk["orders"]!=[] or risk["executable_candidates"]!=[] or risk["historical_PIT_verified"] is not False or risk["official_limit_certified"]!=0 or risk["asof"]!="2026-11-25":raise ValueError("unsafe scope")
    records=[];seen=set()
    for r in risk["records"]:
        if not r["hypotheses"]:continue
        k=(r["code"],r["day"])
        if k in seen:raise ValueError("duplicate risk")
        seen.add(k)
        bands=[x["assumed_band_pct"] for x in r["hypotheses"]]
        records.append(dict(code=r["code"],day=r["day"],hypotheses=r["hypotheses"],classification=classify(r["day"],bands),security_specific_limit_verified=False,fill_verified=False))
    if len(records)!=risk["counts"]["hypothetical_band_matches"]:raise ValueError("incomplete scope")
    return dict(asof=risk["asof"],rule_effective_date=str(EFFECTIVE),official_rule_urls=SOURCES,rule_original_bytes_verified=False,records_count=len(records),counts=dict(Counter(r["classification"] for r in records)),official_limit_certified=0,historical_ST_verified=False,historical_PIT_verified=False,execution_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--risk",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.risk.read_bytes()));a.out.write_text(json.dumps(r,indent=2)+"\n");print("P4_LIMIT_RULE_OVERLAY:",json.dumps({k:v for k,v in r.items() if k!="records"}))
