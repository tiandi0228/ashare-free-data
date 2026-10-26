"""Replay durable original PDF SHA across P3 runs and construct *research* event chains.

An issuer PDF's dated event text does not prove historical first publication,
actual exchange state intervals, or trading eligibility. Missing resume text in
this bounded archive NEVER means the security remained suspended in reality.
"""
import argparse,json,re
from collections import defaultdict
from datetime import date
from pathlib import Path
from collector.p3_official_original_archive import verify_archive

SHA=re.compile(r"[0-9a-f]{64}\Z")
CHINA_DAY=re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\Z")
KNOWN={"HALT_START","RESUME_START","ST_APPLIED","ST_REMOVED",
       "LISTING_START","DELIST_EFFECTIVE"}
MAX_RUNS=500
MAX_CLAIMS=10000

def _day(text):
    match=CHINA_DAY.fullmatch(text if isinstance(text,str) else "")
    if not match:raise ValueError("invalid Chinese effective-text date")
    return date(*map(int,match.groups()))

def build(root):
    root=Path(root)
    folder=root/"runs"
    manifests=sorted(folder.glob("*.json"))
    if not 1<=len(manifests)<=MAX_RUNS:raise ValueError("invalid bounded original archive run count")
    seen_notices={};claims={};raw_claims=0
    source_sha_digests=set()
    for manifest_path in manifests:
        if not manifest_path.stem.isdigit():raise ValueError("unexpected manifest filename")
        run_id=int(manifest_path.stem)
        verified=verify_archive(root,run_id)
        if verified.get("trade_gate")!="BLOCKED" or verified.get("historical_PIT_verified") is not False:
            raise ValueError("original SHA replay gate violated")
        manifest=json.loads(manifest_path.read_text())
        if manifest.get("run_id")!=run_id or manifest.get("historical_PIT_verified") is not False:
            raise ValueError("wrong immutable run identity")
        issuer_digest=manifest.get("source_roster_sha256")
        if not isinstance(issuer_digest,str) or not SHA.fullmatch(issuer_digest):
            raise ValueError("P1 source epoch SHA missing")
        source_sha_digests.add(issuer_digest)
        for receipt in manifest["source_pdf_receipts"]:
            if not receipt.get("original_retrieved"):continue
            key=(receipt.get("issuer"),str(receipt.get("announcement_id")))
            digest=receipt.get("pdf_sha256")
            if not isinstance(digest,str) or not SHA.fullmatch(digest):
                raise ValueError("malformed saved original SHA")
            if key in seen_notices and seen_notices[key]!=digest:
                raise ValueError("same issuer announcement ID has conflicting archived originals")
            seen_notices[key]=digest
        for row in manifest["research_date_action_links"]:
            direction=row.get("local_textual_direction_candidate")
            if direction is None:continue
            if direction not in KNOWN:raise ValueError("unknown event action")
            if any(row.get(k) is not False for k in
                   ("effective_date_authenticated","first_publication_authenticated",
                    "decision_time_available_certified")):
                raise ValueError("unverified text promoted to PIT")
            orig=(row.get("issuer"),str(row.get("announcement_id")))
            if orig not in seen_notices or seen_notices[orig]!=row.get("original_pdf_sha256"):
                raise ValueError("source claim not anchored to original SHA")
            if not isinstance(row.get("source_clause_excerpt"),str):
                raise ValueError("missing source excerpt")
            day=_day(row.get("source_date_text"))
            if row["source_date_text"] not in row["source_clause_excerpt"]:
                raise ValueError("source excerpt does not contain date")
            decision=date.fromisoformat(row["decision_day"])
            claim_key=(orig,day,direction)
            raw_claims+=1
            if raw_claims>MAX_CLAIMS:raise ValueError("unbounded multi-run research claims")
            previous=claims.get(claim_key)
            if previous:
                if previous["original_pdf_sha256"]!=row["original_pdf_sha256"]:
                    raise ValueError("conflicting identical event source identity")
                previous["seen_in_run_ids"].append(run_id)
                previous["decision_days_observed"].add(decision.isoformat())
            else:
                approval_caution=direction in ("ST_APPLIED","ST_REMOVED") and bool(
                    re.search(r"(?:同意|批准|核准|申请|受理)",row["source_clause_excerpt"]))
                claims[claim_key]={
                    "issuer":orig[0],"announcement_id":orig[1],
                    "original_pdf_sha256":row["original_pdf_sha256"],
                    "claimed_event_day":day.isoformat(),
                    "textual_direction":direction,
                    "source_clause_excerpt":row["source_clause_excerpt"],
                    "approval_not_effective_risk":approval_caution,
                    "seen_in_run_ids":[run_id],
                    "decision_days_observed":{decision.isoformat()},
                    "first_publication_authenticated":False,
                    "effective_date_certified":False,
                    "historical_asof_trade_eligible":False}
    if raw_claims<len(claims):raise ValueError("research claim accounting impossible")
    ordered=sorted(claims.values(),key=lambda e:(e["issuer"],e["claimed_event_day"],
                e["announcement_id"],e["textual_direction"]))
    for item in ordered:
        item["seen_in_run_ids"]=sorted(set(item["seen_in_run_ids"]))
        item["decision_days_observed"]=sorted(item["decision_days_observed"])
        item["source_text_date_is_not_complete_interval_proof"]=True
    by_issuer=defaultdict(list)
    for item in ordered:
        if item["textual_direction"] in ("HALT_START","RESUME_START"):
            by_issuer[item["issuer"]].append(item)
    paired=[];missing_resume=[];resume_without_start=[];overlap=[]
    for issuer,events in sorted(by_issuer.items()):
        opened=None
        for event in events:
            if event["textual_direction"]=="HALT_START":
                if opened is not None:
                    overlap.append({"issuer":issuer,"previous_announcement":opened["announcement_id"],
                                    "next_announcement":event["announcement_id"],
                                    "research_warning":"REPEATED_HALT_WITHOUT_OBSERVED_RESUME_IN_BOUNDED_SAMPLE"})
                    # Keep the earlier start as a pending search. Do not silently
                    # move its effective day or assume actual continuous suspension.
                else:
                    opened=event
            else:
                if opened is None:
                    resume_without_start.append({"issuer":issuer,
                        "resumption_day_text":event["claimed_event_day"],
                        "research_warning":"RESUME_WITHOUT_ARCHIVED_HALT_SOURCE"})
                else:
                    if event["claimed_event_day"]<opened["claimed_event_day"]:
                        raise ValueError("chronological halt/resume inconsistency")
                    paired.append({"issuer":issuer,
                        "halt_pdf_sha256":opened["original_pdf_sha256"],
                        "resume_pdf_sha256":event["original_pdf_sha256"],
                        "halt_text_date":opened["claimed_event_day"],
                        "resume_text_date":event["claimed_event_day"],
                        "status":"TWO_UNVERIFIED_TEXT_ASSERTIONS_NOT_CONTINUOUS_OFFICIAL_STATE",
                        "historical_first_publication_authenticated":False,
                        "issuer_interval_certified":False})
                    opened=None
        if opened is not None:
            missing_resume.append({"issuer":issuer,
                "halt_text_date":opened["claimed_event_day"],
                "halt_announcement_id":opened["announcement_id"],
                "original_pdf_sha256":opened["original_pdf_sha256"],
                "followup_research":"SEARCH_OFFICIAL_RESUME_AND_EXCHANGE_STATUS_DOCUMENTS",
                "warning":"NO_RESUME_IN_BOUNDED_ARCHIVE_IS_NOT_PROOF_OF_CONTINUING_HALT",
                "historical_halt_interval_certified":False})
    return {"phase":"P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH",
        "runs_replayed":len(manifests),"source_roster_epochs_observed":len(source_sha_digests),
        "unique_original_pdfs_sha_replayed":len(seen_notices),
        "raw_text_assertion_references":raw_claims,
        "deduplicated_text_event_claims":len(ordered),
        "duplicate_research_references_collapsed":raw_claims-len(ordered),
        "unpaired_halt_starts_needing_resumption_search":len(missing_resume),
        "paired_halt_resume_text_claims_unverified":len(paired),
        "unpaired_resume_claims":len(resume_without_start),
        "overlapping_halt_claims_without_resume":len(overlap),
        "approval_consent_is_not_effective_date_count":sum(e["approval_not_effective_risk"] for e in ordered),
        "research_text_event_claims":ordered,
        "official_resumption_followups":missing_resume,
        "paired_event_texts":paired,
        "orphan_resume_texts":resume_without_start,
        "overlap_conflicts":overlap,
        "historical_first_publication_authenticated":False,
        "complete_issuer_halt_intervals_certified":False,
        "official_PIT_cells_certified":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    args=p.parse_args()
    result=build(args.root)
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in
       ("research_text_event_claims","official_resumption_followups","paired_event_texts",
        "orphan_resume_texts","overlap_conflicts")},ensure_ascii=False))
if __name__=="__main__":main()
