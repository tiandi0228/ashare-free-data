"""Join real SHA-replayed archived P2 page rankings with P3 dated ST guard.

This is a real archived-bar *research* candidate-producing adapter, not an
executable recommendation or a backtest. Historical non-ST certification
remains unavailable for every issuer. Fail closed if 600363 is not covered
in the page, its original P2 gap disappears, or source lineage changes.
"""
import argparse
import json
from pathlib import Path
from collector.p2_real_archive_research_screen import screen
from collector.p4_historical_st_research_veto import classify

PHASE="P4_REAL_ARCHIVED_RESEARCH_SCREEN_ST_REVIEW_NONEXECUTABLE"
EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
ST_SHA="e4c01fa609951f30d25ec28ff729fa862c4815eca4ae279c9d7aeb1940f0fee2"

def integrate(page,crosswalk,triage):
    if (not isinstance(page,dict) or not isinstance(triage,dict)
        or page.get("phase")!="P2_PAGED_REAL_ARCHIVE_FEATURE_REPLAY"
        or page.get("status")!="PAGED_REAL_ARCHIVE_RESEARCH_ONLY"
        or page.get("source_epoch_sha256")!=EPOCH
        or page.get("asof_completed_day")!="2026-10-20"
        or page.get("historical_PIT_verified") is not False
        or page.get("trade_gate")!="BLOCKED"
        or page.get("orders")!=[] or page.get("executable_candidates")!=[]
        or page.get("actionable_buy_signals")!=[]
        or "shard_0033" not in page.get("selected_shards",[])
        or triage.get("phase")!="P2_ORIGINAL_SHA_VERIFIED_FEATURE_GAP_RESEARCH_TRIAGE"
        or triage.get("source_epoch_sha256")!=EPOCH
        or triage.get("trade_gate")!="BLOCKED"
        or triage.get("historical_PIT_verified") is not False):
        raise ValueError("wrong archive epoch, page or risk evidence")
    original=[x for x in triage.get("research_actions",[])
              if x.get("issuer")=="sh.600363"]
    if (len(original)!=1 or original[0].get("shard_id")!="shard_0033"
        or original[0].get("original_csv_sha256")!=ST_SHA
        or original[0].get("gap_resolved") is not False):
        raise ValueError("original ST-issuer SHA gap unavailable")
    gaps=page.get("evidence_gaps")
    if (not isinstance(gaps,list)
        or len([g for g in gaps if g.get("issuer")=="sh.600363"
                and g.get("reason")=="INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"])!=1):
        raise ValueError("600363 SHA-bound vendor gap not present in actual page")
    ranking=screen(page)
    if (ranking.get("status")!="DESCRIPTIVE_ARCHIVED_SAMPLE_ONLY"
        or ranking.get("source_epoch_sha256")!=EPOCH
        or ranking.get("trade_gate")!="BLOCKED"
        or ranking.get("orders")!=[]
        or ranking.get("executable_candidates")!=[]
        or ranking.get("historical_PIT_verified") is not False
        or ranking.get("scoped_issuers")!=page.get("scoped_verified_issuers")):
        raise ValueError("real descriptive ranking not independently accepted")
    codes=[x["issuer"] for x in ranking["descriptive_order"]]
    if len(codes)!=len(set(codes)) or "sh.600363" in codes:
        raise ValueError("suspended/ST issuer was ranked")
    # The frozen risk classifier accepts at most 100 observations per call.
    # Chunk actual ranked page issuers without dropping the tail.
    by={}
    batches=[codes[i:i+90] for i in range(0,len(codes),90)]
    if not batches:batches=[[]]
    for batch_index, batch in enumerate(batches):
        selected=list(batch)
        if batch_index==0:
            selected.append("sh.600363")
        records=[{"issuer":issuer,
                  "signal_known_after_close_date":page["asof_completed_day"],
                  "research_only":True,"buy_signal":False}
                 for issuer in selected]
        veto=classify(crosswalk,records)
        if (veto.get("historical_PIT_verified") is not False
            or veto.get("trade_gate")!="BLOCKED"
            or veto.get("approved_entries")!=0
            or veto.get("orders")!=[]
            or len(veto.get("research_decisions",[]))!=len(records)):
            raise ValueError("untrusted risk screening")
        for row in veto["research_decisions"]:
            code=row["issuer"]
            if code in by:raise ValueError("duplicate risk-audited issuer")
            by[code]=row
    if (len(by)!=len(codes)+1
        or by["sh.600363"]["candidate_policy_research_state"]!="VETO_ISSUER_NOTICE_ST_EFFECTIVE"
        or any(by[k]["candidate_policy_research_state"]!="UNKNOWN_PIT_STATUS_FAIL_CLOSED"
               for k in codes)):
        raise ValueError("unexpected PIT status for actual features")
    return {
        "phase":PHASE,"source_epoch_sha256":EPOCH,
        "source_archive_git_sha":page["archive_commit_sha"],
        "source_page_index":page["page_index"],
        "source_selected_shards":page["selected_shards"],
        "original_600363_csv_sha256":ST_SHA,
        "asof_completed_day":page["asof_completed_day"],
        "real_archived_page_issuer_count":page["scoped_verified_issuers"],
        "descriptive_ranked_original_issuers":len(codes),
        "source_feature_gap_issuers":len(gaps),
        "st_600363_source_gap_held_out_of_ranking":True,
        "st_600363_dated_veto_verified_in_research":True,
        "other_issuer_PIT_unknown_rejected":len(codes),
        "candidate_approvals":0,
        "real_original_candidate_rows":[{
            "issuer":item["issuer"],
            "source_original_sha256":item["source_original_sha256"],
            "descriptive_score":item["descriptive_score"],
            "risk_rejection_reason":by[item["issuer"]]["candidate_policy_research_state"],
            "approved_for_entry":False,
        } for item in ranking["descriptive_order"]],
        "historical_PIT_verified":False,
        "production_candidate_pipeline_integrated":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    a=argparse.ArgumentParser()
    for name in ("page","crosswalk","triage","out"):
        a.add_argument("--"+name,required=True,type=Path)
    v=a.parse_args()
    result=integrate(json.loads(v.page.read_text()),json.loads(v.crosswalk.read_text()),
                     json.loads(v.triage.read_text()))
    v.out.parent.mkdir(parents=True,exist_ok=True)
    v.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("phase",
        "real_archived_page_issuer_count","descriptive_ranked_original_issuers",
        "source_feature_gap_issuers","st_600363_source_gap_held_out_of_ranking",
        "candidate_approvals","trade_gate")},sort_keys=True))
if __name__=="__main__":main()
