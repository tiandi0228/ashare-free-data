"""Temporal sanity review of append-only SHA-backed P3 official PDF research.

An issuer announcement's text can describe an event on one date and a
decision on another. Consent/approval is not a confirmed state transition.
This report NEVER certifies publication, effectiveness, issuer intervals
or the user's historical ability to trade.
"""
import argparse,json,re
from datetime import date
from pathlib import Path
DATE=re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\Z")
DIRECTIONS={"HALT_START","RESUME_START","ST_APPLIED","ST_REMOVED",
            "LISTING_START","DELIST_EFFECTIVE"}
def audit(manifest):
    if (manifest.get("phase")!="P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE"
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("historical_PIT_verified") is not False
        or manifest.get("orders")!=[]
        or any(manifest.get(x)!=0 for x in
               ("certified_first_publication_count","certified_event_effective_day_count",
                "certified_historical_decision_state_count"))):
        raise ValueError("unsafe official original archival claim")
    rows=manifest.get("research_date_action_links")
    if not isinstance(rows,list):raise ValueError("missing real research links")
    flags_by_lead=[];candidate_count=0;needs_date_check=0;approval_flags=0
    for row in rows:
        if any(row.get(k) is not False for k in ("effective_date_authenticated",
                "first_publication_authenticated","decision_time_available_certified")):
            raise ValueError("unjustified source certification")
        direction=row.get("local_textual_direction_candidate")
        if direction is None:continue
        if direction not in DIRECTIONS:raise ValueError("unknown source direction")
        candidate_count+=1
        m=DATE.fullmatch(row.get("source_date_text",""))
        if not m:raise ValueError("malformed original PDF date text")
        try:claimed_day=date(*map(int,m.groups()))
        except ValueError as e:raise ValueError("invalid PDF date") from e
        decision_day=date.fromisoformat(row["decision_day"])
        excerpt=row.get("source_clause_excerpt")
        if not isinstance(excerpt,str) or not excerpt.strip() or row["source_date_text"] not in excerpt:
            raise ValueError("no exact original event clause")
        checks=["FIRST_PUBLICATION_TIME_NOT_INDEPENDENTLY_AUTHENTICATED",
                "CONTINUOUS_HISTORICAL_ISSUER_STATE_NOT_CERTIFIED"]
        delta=(claimed_day-decision_day).days
        if delta!=0:
            checks.append("CLAIMED_TEXT_DATE_NOT_DECISION_DAY")
            needs_date_check+=1
        if direction in ("ST_APPLIED","ST_REMOVED") and re.search(r"(?:同意|批准|核准|申请|受理)",excerpt):
            checks.append("APPROVAL_OR_APPLICATION_NOT_STATE_EFFECTIVE_DAY")
            approval_flags+=1
        time_hint=row.get("index_time_screen")
        if time_hint=="INDEX_TIME_AFTER_DECISION_CLOSE_UNVERIFIED":
            checks.append("INDEX_METADATA_AFTER_DECISION_CLOSE")
        if not isinstance(time_hint,str) or not time_hint.endswith("_UNVERIFIED"):
            raise ValueError("index claimed timestamp treated as certified")
        flags_by_lead.append({"issuer":row["issuer"],"announcement_id":row["announcement_id"],
            "decision_day":decision_day.isoformat(),
            "text_claim_date":claimed_day.isoformat(),
            "claim_minus_decision_calendar_days":delta,
            "text_direction":direction,
            "original_pdf_sha256":row["original_pdf_sha256"],
            "research_cautions":checks,
            "effective_date_certified":False,
            "first_publication_certified":False,
            "full_interval_state_certified":False,
            "decision_day_trade_allowed":False})
    if candidate_count!=manifest.get("explicit_local_textual_candidate_count"):
        raise ValueError("candidate tally differs from archived original manifest")
    return {"phase":"P3_PERSISTED_PDF_TEMPORAL_RISK_TRIAGE",
        "source_run_id":manifest["run_id"],
        "explicit_textual_candidate_count":candidate_count,
        "candidate_with_text_date_not_decision_day":needs_date_check,
        "candidate_with_approval_not_effective_date":approval_flags,
        "original_sha_linked_manual_review":flags_by_lead,
        "independently_authenticated_first_publication":0,
        "certified_event_effective_dates":0,
        "certified_historical_interval_states":0,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True);p.add_argument("--out",required=True)
    x=p.parse_args()
    q=audit(json.loads(Path(x.manifest).read_text()))
    file=Path(x.out);file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in q.items() if k!="original_sha_linked_manual_review"},ensure_ascii=False))
if __name__=="__main__":main()
