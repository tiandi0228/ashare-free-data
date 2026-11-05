"""Reviewer-ready, independently checked P3 source locators (NOT PIT evidence)."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

PHASE = "P3_OFFICIAL_PROOF_MANUAL_REVIEW_PACKET"
SHA = re.compile(r"[a-f0-9]{64}\Z")
ISSUER = re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")
KINDS = {
    "CONFLICT_REQUIRES_ORIGINAL_REVIEW": "REVIEW_REPEATED_HALT_TEXT_AND_OFFICIAL_EXCHANGE_STATE",
    "INDEPENDENT_TIME_AND_INTERVAL_EVIDENCE": "FIND_INDEPENDENT_FIRST_PUBLICATION_AND_EFFECTIVE_INTERVAL",
    "MISSING_RESUMPTION_SOURCE": "FIND_INDEPENDENT_OFFICIAL_RESUMPTION_SOURCE",
    "MISSING_HALT_SOURCE": "FIND_INDEPENDENT_OFFICIAL_HALT_SOURCE",
}
MAX = 10000


def _source(issuer, notice, digest, anchor, day):
    if (not isinstance(issuer, str) or not ISSUER.fullmatch(issuer)
            or not isinstance(notice, str) or not notice.isdigit()
            or not isinstance(digest, str) or not SHA.fullmatch(digest)
            or not isinstance(anchor, dict)
            or anchor.get("sha_verified_original_archive_path") !=
            f"pdf/{issuer.replace('.', '_')}/{notice}/{digest}.pdf"
            or anchor.get("official_first_publication_authenticated") is not False
            or type(anchor.get("first_archived_original_run_id")) is not int
            or anchor["first_archived_original_run_id"] < 1
            or not isinstance(anchor.get("first_archived_research_capture_utc_not_first_publication"), str)
            or not isinstance(day, str)
            or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", day)):
        raise ValueError("untrusted SHA-linked research-original locator")
    return {
        "announcement_id": notice,
        "original_pdf_sha256": digest,
        "original_archive_path": anchor["sha_verified_original_archive_path"],
        "first_research_capture_utc_not_publication":
            anchor["first_archived_research_capture_utc_not_first_publication"],
        "original_run_id": anchor["first_archived_original_run_id"],
        "original_text_event_day_unverified": day,
        "official_first_publication_authenticated": False,
    }


def _origins(row):
    ev=row["original_research_review_evidence"]
    issuer=row["issuer"]
    kind=row["review_bucket"]
    if not isinstance(ev, dict):
        raise ValueError("no original evidence")
    if kind=="MISSING_HALT_SOURCE":
        if set(ev)!={"resume_text_day_unverified"}:
            raise ValueError("orphan is unpinned; do not invent PDF original")
        return [], "UNPAIRED_RESUMPTION_TEXT_UNPINNED_IN_SOURCE_QUEUE"
    if kind=="MISSING_RESUMPTION_SOURCE":
        return [_source(issuer,ev.get("halt_announcement_id"),
                        ev.get("halt_pdf_sha256"),ev.get("halt_original_archive_capture"),
                        ev.get("halt_text_day_unverified"))], None
    if kind=="INDEPENDENT_TIME_AND_INTERVAL_EVIDENCE":
        return [
            _source(issuer,ev.get("halt_announcement_id"),ev.get("halt_pdf_sha256"),
                    ev.get("halt_original_archive_capture"),ev.get("halt_text_day_unverified")),
            _source(issuer,ev.get("resume_announcement_id"),ev.get("resume_pdf_sha256"),
                    ev.get("resume_original_archive_capture"),ev.get("resume_text_day_unverified"))
        ], None
    if kind=="CONFLICT_REQUIRES_ORIGINAL_REVIEW":
        output=[]
        for prefix in ("previous","next"):
            cands=ev.get(prefix+"_halt_original_sha_and_text_day_candidates")
            if not isinstance(cands,list) or not 1<=len(cands)<=20:
                raise ValueError("repeated-halt original candidate set missing")
            notice=ev.get(prefix+"_announcement_id")
            for c in cands:
                if not isinstance(c,dict) or c.get("source_announcement_id")!=notice:
                    raise ValueError("conflict source ID changed")
                output.append(_source(
                    issuer,notice,c.get("original_pdf_sha256"),
                    c.get("archived_research_original_capture"),
                    c.get("source_halt_text_day_unverified")))
        if ev.get("same_announcement_id_reused_in_halt_conflict") is not (
                ev.get("previous_announcement_id")==ev.get("next_announcement_id")):
            raise ValueError("conflict original ambiguity rewritten")
        return output, "CONFLICT_CANDIDATES_NOT_INDEPENDENT_LEGAL_EVENTS"
    raise ValueError("unknown review class")


def build(report):
    if (not isinstance(report,dict)
        or report.get("phase")!="P3_UNCERTIFIED_PROOF_GAP_TRIAGE"
        or report.get("status")!="TRIAGED_NOT_CERTIFIED"
        or report.get("trade_gate")!="BLOCKED"
        or report.get("historical_PIT_verified") is not False
        or report.get("orders")!=[] or report.get("recommendations")!=[]
        or report.get("executable_candidates")!=[]
        or any(report.get(k)!=0 for k in (
            "official_first_publication_authenticated","official_state_intervals_certified"))):
        raise ValueError("unsafe triage source")
    items=report.get("work_items")
    if (not isinstance(items,list) or len(items)>MAX
        or type(report.get("total_unresolved_work_items")) is not int
        or report["total_unresolved_work_items"]!=len(items)
        or not isinstance(report.get("review_bucket_counts"),dict)):
        raise ValueError("truncated P3 source")
    result=[]; seen=set()
    for position,row in enumerate(items):
        if (not isinstance(row,dict) or row.get("queue_index")!=position
            or row.get("review_bucket") not in KINDS
            or row.get("official_evidence_status")!="NOT_AUTHENTICATED"
            or row.get("eligible_for_historical_trade_replay") is not False
            or row.get("original_research_is_not_first_publication_proof") is not True
            or row.get("priority") not in (0,1,2,3)
            or not isinstance(row.get("issuer"),str)
            or not ISSUER.fullmatch(row["issuer"])
            or not isinstance(row.get("missing_independent_proofs"),list)
            or not row["missing_independent_proofs"]):
            raise ValueError("forged or incomplete evidence gap")
        sources, warning=_origins(row)
        canonical=json.dumps({"index":position,"kind":row["review_bucket"],
                              "issuer":row["issuer"],"sources":sources},
                             sort_keys=True,separators=(",",":"))
        task_id=hashlib.sha256(canonical.encode()).hexdigest()[:20]
        if task_id in seen:
            raise ValueError("duplicate source review task")
        seen.add(task_id)
        result.append({
            "task_id":task_id,"queue_index":position,"issuer":row["issuer"],
            "priority":row["priority"],"review_bucket":row["review_bucket"],
            "next_review_action":KINDS[row["review_bucket"]],
            "missing_independent_proofs":row["missing_independent_proofs"],
            "archived_research_originals_not_publication_proof":sources,
            "source_limitations":warning,
            "review_status":"NEEDS_INDEPENDENT_OFFICIAL_EVIDENCE",
            "historical_PIT_verified":False,"trade_eligible":False,
        })
    counts=dict(sorted(Counter(row["review_bucket"] for row in result).items()))
    if counts!=report["review_bucket_counts"]:
        raise ValueError("P3 source bucket count disagreement")
    return {
        "phase":PHASE,"status":"MANUAL_EVIDENCE_REQUESTS_NOT_CERTIFICATIONS",
        "source_phase":report["phase"],"total_review_tasks":len(result),
        "review_bucket_counts":counts,"tasks":result,
        "authenticated_first_publication_count":0,
        "certified_historical_state_intervals":0,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"recommendations":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--triage",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--csv",type=Path,required=True)
    args=p.parse_args()
    packet=build(json.loads(args.triage.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.csv.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with args.csv.open("w",newline="",encoding="utf-8-sig") as fp:
        writer=csv.writer(fp)
        writer.writerow(("task_id","queue_index","issuer","priority","review_bucket",
                         "next_review_action","source_announcements_and_sha",
                         "missing_independent_proofs","status"))
        for row in packet["tasks"]:
            sources=row["archived_research_originals_not_publication_proof"]
            # Quote plain source data; CSV is a triage index, never proof itself.
            writer.writerow((row["task_id"],row["queue_index"],row["issuer"],
                             row["priority"],row["review_bucket"],row["next_review_action"],
                             "; ".join(s["announcement_id"]+":"+s["original_pdf_sha256"] for s in sources),
                             "; ".join(row["missing_independent_proofs"]),
                             row["review_status"]))
    print(json.dumps({"total_review_tasks":packet["total_review_tasks"],
                      "review_bucket_counts":packet["review_bucket_counts"],
                      "trade_gate":packet["trade_gate"]}))


if __name__=="__main__":
    main()
