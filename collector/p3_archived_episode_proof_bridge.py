"""Turn SHA-replayed P3 archival *text candidates* into blocked proof tasks.

The candidate's stated date is not a certified exchange effective date.
No research capture timestamp is promoted into a historical first-publication
timestamp, issuer state or trading authorization.
"""
import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from collector.p3_publication_asof_gate import assess, instant
from collector.p3_publication_proof_task_queue import build as build_tasks

SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")
ACTIONS = {"HALT_START","RESUME_START","ST_APPLIED","ST_REMOVED",
           "LISTING_START","DELIST_EFFECTIVE"}


def bridge(source, decision_instant):
    instant(decision_instant)
    if (not isinstance(source,dict)
        or source.get("phase")!="P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH"
        or source.get("trade_gate")!="BLOCKED"
        or source.get("orders")!=[]
        or source.get("executable_candidates")!=[]
        or source.get("historical_PIT_verified") is not False
        or source.get("historical_first_publication_authenticated") is not False
        or source.get("complete_issuer_halt_intervals_certified") is not False
        or source.get("official_PIT_cells_certified")!=0):
        raise ValueError("unsafe or unsupported durable episode evidence")
    claims=source.get("research_text_event_claims")
    if (not isinstance(claims,list) or len(claims)>10000
        or type(source.get("deduplicated_text_event_claims")) is not int
        or len(claims)!=source["deduplicated_text_event_claims"]):
        raise ValueError("wrong event claim count")
    events=[]
    seen=set()
    for claim in claims:
        if not isinstance(claim,dict):
            raise ValueError("malformed archived event claim")
        issuer,digest,kind,day=(claim.get("issuer"),
            claim.get("original_pdf_sha256"),claim.get("textual_direction"),
            claim.get("claimed_event_day"))
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or kind not in ACTIONS or not isinstance(day,str)
            or date.fromisoformat(day).isoformat()!=day
            or claim.get("first_publication_authenticated") is not False
            or claim.get("effective_date_certified") is not False
            or claim.get("historical_asof_trade_eligible") is not False
            or claim.get("source_text_date_is_not_complete_interval_proof") is not True
            or claim.get("research_capture_not_official_first_publication") is not True
            or type(claim.get("original_first_archived_research_run_id")) is not int
            or claim["original_first_archived_research_run_id"]<=0):
            raise ValueError("untrusted or promoted archived text candidate")
        expected=f"pdf/{issuer.replace('.','_')}/{claim.get('announcement_id')}/{digest}.pdf"
        if claim.get("original_sha_verified_archive_path")!=expected:
            raise ValueError("original archive path not pinned to digest")
        capture=claim.get("original_first_archived_research_capture_at_utc")
        if not isinstance(capture,str) or not capture.endswith("+00:00"):
            raise ValueError("archived original capture must be UTC")
        instant(capture)
        key=(issuer,kind,digest)
        if key in seen:
            # Current as-of model cannot distinguish repeated same-origin claims;
            # reject ambiguity rather than silently discarding one date.
            raise ValueError("ambiguous source claim identity")
        seen.add(key)
        events.append({
            "issuer":issuer,"kind":kind,"original_sha256":digest,
            "effective_date":day, # UNVERIFIED SOURCE TEXT ONLY
            "authenticated_first_published_at":None,
            "publisher_independently_authenticated":False,
            "original_bytes_verified":True,
            "publication_timestamp_independently_authenticated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        })
    asof=assess(events,decision_instant)
    queue=build_tasks(asof)
    if queue["task_count"]!=len(claims):
        raise ValueError("archived claims vanished in proof bridge")
    return {
        "phase":"P3_ARCHIVED_TEXT_TO_PUBLICATION_PROOF_QUEUE",
        "source_phase":source["phase"],
        "source_text_dates_are_not_official_effective_dates":True,
        "original_capture_is_not_first_publication":True,
        "research_issuer_claims":len(claims),
        "publication_asof":asof,
        "proof_queue":queue,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--episode",required=True,type=Path)
    parser.add_argument("--decision-instant",required=True)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    output=bridge(json.loads(args.episode.read_text()),args.decision_instant)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        "phase":output["phase"],
        "research_issuer_claims":output["research_issuer_claims"],
        "task_count":output["proof_queue"]["task_count"],
        "task_counts_by_missing_proof":output["proof_queue"]["task_counts_by_missing_proof"],
        "historical_PIT_verified":False,"trade_gate":"BLOCKED"},ensure_ascii=False))


if __name__=="__main__":
    main()
