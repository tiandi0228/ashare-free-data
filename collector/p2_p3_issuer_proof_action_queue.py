"""Per-issuer P2/P3 original-evidence follow-up queue, strictly research-only.

Translate verified crosswalk state into explicit, testable manual source tasks.
Same-issuer original PDF text and even text pairs do not authenticate first
publication, exchange halt intervals, vendor calendar rows or PIT eligibility.
"""
import argparse
import json
import re
from pathlib import Path

ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
CATEGORIES=(
    "VERIFY_VENDOR_HISTORY_AND_LISTING_EVIDENCE",
    "FIND_ORIGINAL_HALT_RESUME_ANNOUNCEMENTS",
    "FIND_MATCHING_RESUME_ORIGINAL_AND_CHRONOLOGY",
    "AUTHENTICATE_BOTH_ORIGINAL_PUBLICATION_TIMES_AND_EFFECTIVE_INTERVAL",
)


def build(crosswalk,guard):
    if (not isinstance(crosswalk,dict)
        or crosswalk.get("phase")!="P2_P3_SAME_ISSUER_RESEARCH_GAP_CROSSWALK"
        or crosswalk.get("status")!="RESEARCH_JOIN_NO_PIT_EVENT_CAUSATION"
        or crosswalk.get("trade_gate")!="BLOCKED"
        or crosswalk.get("orders")!=[]
        or crosswalk.get("executable_candidates")!=[]
        or crosswalk.get("actionable_buy_signals")!=[]
        or crosswalk.get("historical_PIT_verified") is not False
        or crosswalk.get("official_halt_intervals_authenticated")!=0
        or crosswalk.get("feature_gaps_resolved")!=0
        or not isinstance(guard,dict)
        or guard.get("phase")!="P2_P3_CURRENT_RESEARCH_SOURCE_CROSSWALK_GUARD"
        or guard.get("status")!="SAME_P1_EPOCH_SOURCE_BOUNDED_RESEARCH_ONLY"
        or guard.get("trade_gate")!="BLOCKED"
        or guard.get("orders")!=[]
        or guard.get("historical_PIT_verified") is not False
        or guard.get("P3_event_text_is_official_halt_authentication") is not False):
        raise ValueError("unsafe crosswalk or provenance guard")
    epoch=guard.get("source_epoch_sha256")
    if (not isinstance(epoch,str) or not SHA.fullmatch(epoch)
        or crosswalk.get("source_epoch_sha256")!=epoch):
        raise ValueError("P2/P3 crosswalk P1 epoch SHA mismatch")
    rows=crosswalk.get("issuer_evidence")
    codes=guard.get("issuer_codes")
    if (not isinstance(rows,list) or not 1<=len(rows)<=1000
        or not isinstance(codes,list) or codes!=sorted(set(codes))
        or not all(isinstance(code,str) and ISSUER.fullmatch(code) for code in codes)
        or len(rows)!=len(codes)
        or crosswalk.get("gap_issuers_examined")!=len(codes)
        or guard.get("p2_vendor_gap_issuers")!=len(codes)):
        raise ValueError("crosswalk issuer count or order inconsistent")
    planned=[];observed=set();with_leads=0;with_pairs=0
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError("invalid original research gap row")
        issuer=row.get("issuer")
        leads=row.get("same_issuer_official_pdf_text_leads")
        pairs=row.get("same_issuer_sha_linked_resume_text_pairs")
        if (issuer not in codes or issuer in observed
            or type(leads) is not int or not 0<=leads<=10000
            or type(pairs) is not int or not 0<=pairs<=10000
            or row.get("vendor_gap_diagnosis") not in (
                "VENDOR_SUSPENDED_ROW_WITHIN_LAST_21",
                "FEWER_THAN_21_VENDOR_ROWS_ASOF")
            or not isinstance(row.get("vendor_csv_sha256"),str)
            or not SHA.fullmatch(row["vendor_csv_sha256"])
            or row.get("official_trading_state_covered_for_gap") is not False
            or row.get("gap_resolved") is not False):
            raise ValueError("forged or malformed gap research evidence")
        observed.add(issuer)
        with_leads+=int(leads>0)
        with_pairs+=int(pairs>0)
        diagnosis=row["vendor_gap_diagnosis"]
        if diagnosis=="FEWER_THAN_21_VENDOR_ROWS_ASOF":
            action=CATEGORIES[0]
        elif leads==0 and pairs==0:
            action=CATEGORIES[1]
        elif pairs==0:
            action=CATEGORIES[2]
        else:
            action=CATEGORIES[3]
        if leads==0 and pairs>0:
            # A historical text pair can exist when the current bounded event
            # projection has no event lead. Do not assert a negative source
            # finding: first authenticate the pair's original provenance.
            action=CATEGORIES[3]
        planned.append({
            "issuer":issuer,
            "source_epoch_sha256":epoch,
            "original_vendor_csv_sha256":row["vendor_csv_sha256"],
            "vendor_gap_diagnosis":diagnosis,
            "official_pdf_halt_resume_text_leads":leads,
            "research_text_resume_pairs":pairs,
            "research_action":action,
            "required_official_evidence":[
                "SOURCE_AUTHENTIC_ORIGINAL_DOCUMENT_SHA",
                "INDEPENDENT_FIRST_PUBLICATION_TIME_AND_SOURCE",
                "EXCHANGE_EFFECTIVE_HALT_RESUME_INTERVAL_OR_LISTING_HISTORY",
                "COMPLETE_POINT_IN_TIME_TRADABILITY_CROSSCHECK"],
            "official_evidence_authenticated":False,
            "historical_PIT_verified":False,
            "feature_gap_resolved":False,
            "buy_eligible":False,
        })
    if (observed!=set(codes)
        or with_leads!=crosswalk.get("gap_issuers_with_same_issuer_official_pdf_text_lead")
        or with_pairs!=crosswalk.get("gap_issuers_with_same_issuer_resume_text_pair")):
        raise ValueError("P2/P3 research classification counts conflict")
    ordered=sorted(planned,key=lambda row:(CATEGORIES.index(row["research_action"]),row["issuer"]))
    counts={key:sum(x["research_action"]==key for x in ordered) for key in CATEGORIES}
    return {
        "phase":"P2_P3_SOURCE_SHA_ISSUER_EVIDENCE_REVIEW_QUEUE",
        "status":"UNRESOLVED_OFFICIAL_PROOF_REQUIREMENTS_RESEARCH_ONLY",
        "source_epoch_sha256":epoch,
        "p2_source_run_id":guard.get("p2_source_run_id"),
        "p3_source_run_id":guard.get("p3_source_run_id"),
        "p1_completed_shards_in_source_scope":guard.get("p2_current_archived_shards"),
        "gap_issuer_count":len(ordered),
        "issuer_with_same_issuer_text_lead":with_leads,
        "issuer_with_resume_text_pair":with_pairs,
        "review_action_counts":counts,
        "tasks":ordered,
        "unresolved_issuer_count":len(ordered),
        "official_halt_intervals_certified":0,
        "feature_gaps_resolved":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--crosswalk",type=Path,required=True)
    p.add_argument("--guard",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    report=build(json.loads(a.crosswalk.read_text()),json.loads(a.guard.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:report[k] for k in (
        "phase","status","gap_issuer_count","review_action_counts",
        "official_halt_intervals_certified","feature_gaps_resolved","trade_gate")},ensure_ascii=False))


if __name__=="__main__":
    main()
