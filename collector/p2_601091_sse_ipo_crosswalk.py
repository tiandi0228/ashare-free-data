"""Research-only official IPO listing-date crosswalk for 601091.

The official SSE listing notice confirms the first listing date; its dated
page does not authenticate the exact initial publication instant, the issuer's
whole day-by-day trading status, or the vendor bars. Never invent pre-IPO
bars or promote an incomplete 21-row feature window.
"""
import argparse
import json
from pathlib import Path

SOURCE_EPOCH = "5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
SSE_NOTICE = "https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/c_20260916_10832340.shtml"
ORIGINAL_SHA = "a99a8383f8a3a41682a7264cac5a1a3097831bb2e456c2c36d09c188b8fcdf3d"
ISSUER = "sh.601091"

def crosswalk(triage):
    if (not isinstance(triage,dict)
        or triage.get("phase")!="P2_ORIGINAL_SHA_VERIFIED_FEATURE_GAP_RESEARCH_TRIAGE"
        or triage.get("source_epoch_sha256")!=SOURCE_EPOCH
        or triage.get("unresolved_issuers")!=16
        or triage.get("unresolved_shards")!=15
        or triage.get("feature_complete_shards")!=226
        or triage.get("observed_shards")!=241
        or triage.get("trade_gate")!="BLOCKED"
        or triage.get("historical_PIT_verified") is not False
        or triage.get("orders")!=[]
        or triage.get("executable_candidates")!=[]):
        raise ValueError("unsafe P2 triage or wrong source epoch")
    records=triage.get("research_actions")
    if not isinstance(records,list) or len(records)!=16:
        raise ValueError("16 unmodified gap records required")
    listing=[r for r in records if r.get("issuer")==ISSUER]
    if len(listing)!=1:
        raise ValueError("IPO source issuer missing or duplicated")
    row=listing[0]
    if (row.get("shard_id")!="shard_0097"
        or row.get("category")!="FEWER_THAN_21_VENDOR_ROWS_ASOF"
        or row.get("vendor_rows")!=18
        or row.get("suspended_rows_last_21")!=0
        or row.get("original_csv_sha256")!=ORIGINAL_SHA
        or row.get("gap_resolved") is not False
        or row.get("eligible_for_feature_complete_promotion") is not False
        or row.get("original_mutation_authorized") is not False):
        raise ValueError("IPO original did not match short-history receipt")
    if sum(r.get("category")=="FEWER_THAN_21_VENDOR_ROWS_ASOF" for r in records)!=1:
        raise ValueError("unaccounted other short-history issuer")
    return {
        "phase":"P2_SH_601091_SSE_IPO_LISTING_RESEARCH_CROSSWALK",
        "issuer":ISSUER,
        "company":"沈鼓集团股份有限公司",
        "source_epoch_sha256":SOURCE_EPOCH,
        "original_csv_sha256":ORIGINAL_SHA,
        "shard":"shard_0097",
        "source_reference":{
            "authority":"上海证券交易所",
            "document":"关于沈鼓集团股份有限公司人民币普通股股票上市交易的公告",
            "document_date":"2026-09-16",
            "notice_number":"上证公告（股票）[2026]31号",
            "official_url":SSE_NOTICE,
            "security_code":"601091",
            "listed_first_day":"2026-09-17",
            "first_publication_instant_authenticated":False,
        },
        "vendor_first_observed_row_day":"2026-09-17",
        "vendor_asof_day":"2026-10-20",
        "vendor_observed_rows":18,
        "minimum_rolling_tradable_bars_required":21,
        "observed_vendor_row_shortfall":3,
        "initial_vendor_row_aligns_listing_date":True,
        "historical_prelisting_bars_permitted":False,
        "gap_classification":"SHORT_POST_IPO_OBSERVATION_WINDOW_NOT_PROVEN_DATA_LOSS",
        "gap_resolved":False,
        "feature_complete_shards_promoted":0,
        "current_official_session_calendar_verified":False,
        "daily_tradability_status_certified":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "next_research_action":"RECHECK_NEWER_REAL_ROWS_ONLY_IF_SOURCE_EPOCH_AND_ASOF_EXPLICITLY_UPDATED",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--gap-triage",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=crosswalk(json.loads(a.gap_triage.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":result["phase"],"issuer":ISSUER,
        "ipo_date":result["source_reference"]["listed_first_day"],
        "gap_resolved":False,"feature_complete_shards_promoted":0,
        "trade_gate":"BLOCKED"},ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
