"""Independent CNINFO missing-index fallback to official SSE delisting pages.

SSE pages confirm separate event content, NOT the missing CNINFO index ID.
"""
import argparse,json
from pathlib import Path

def assess(index, sse):
    if index.get("trade_gate")!="BLOCKED" or sse.get("trade_gate")!="BLOCKED":
        raise ValueError("unsafe source")
    if index.get("historical_PIT_eligible")!=0 or sse.get("historical_point_in_time_universe_verified") is not False:
        raise ValueError("unexpected historical certification")
    if sse.get("issuer")!="sh.600421" or sse.get("attempted_gets")!=2:
        raise ValueError("wrong independent evidence scope")
    pages=sse.get("page_events")
    if not isinstance(pages,list) or len(pages)!=2:
        raise ValueError("missing SSE receipts")
    observed=[p for p in pages if p.get("status")=="OBSERVED_OFFICIAL_HOST_UNVERIFIED_PUBLICATION_TIMING"]
    gaps=index.get("unavailable_or_unmatched",[])
    missing=any(x.get("source_id")=="cninfo_600421_risk_20260619" for x in gaps)
    return {"phase":"P3_CNINFO_SSE_INDEPENDENT_FALLBACK",
            "issuer":"sh.600421","cninfo_index_missing":missing,
            "sse_official_host_events_observed":len(observed),
            "sse_independent_event_types":[x["event"] for x in observed],
            "same_announcement_identity_proven":False,
            "cninfo_missing_id_resolved":False,
            "historical_first_publication_authenticated":False,
            "full_historical_ST_halt_delist_coverage":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--index",required=True);ap.add_argument("--sse",required=True);ap.add_argument("--out",required=True)
    a=ap.parse_args()
    r=assess(json.loads(Path(a.index).read_text()),json.loads(Path(a.sse).read_text()))
    Path(a.out).write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(r,ensure_ascii=False))
if __name__=="__main__":main()
