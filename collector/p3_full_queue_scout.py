"""Bounded official-source research scouting against *all* P1-audited issuers.

This is a discovery bridge, not an official PIT state certification or
a source of tradable orders. Rotate three issuers per new four-shard P1 run.
"""
import argparse,json,re
from collections import defaultdict
from datetime import date
from pathlib import Path

CODE=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
KINDS={"listing","st","halt","delisting"}

def verified_p2_vendor_priority(coverage,queue,by_issuer):
    """Read-only research hint, anchored to P3's independently checked P1 CSV."""
    if coverage is None:
        return []
    if (not isinstance(coverage,dict)
        or coverage.get("phase")!="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
        or coverage.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
        or coverage.get("source_epoch_sha256")!=queue.get("roster_source_sha256")
        or coverage.get("trade_gate")!="BLOCKED"
        or coverage.get("historical_PIT_verified") is not False
        or coverage.get("coverage_certified_for_trading") is not False
        or coverage.get("orders")!=[]
        or coverage.get("executable_candidates")!=[]
        or coverage.get("actionable_buy_signals")!=[]
        or coverage.get("gap_repair_queue_is_research_only") is not True):
        raise ValueError("unsafe or mismatched P2 feature research hint")
    rows=coverage.get("gap_repair_queue")
    if (not isinstance(rows,list) or len(rows)>400
        or len(rows)!=coverage.get("observed_with_feature_gaps_shards")
        or type(coverage.get("issuer_evidence_gap_count")) is not int):
        raise ValueError("invalid P2 gap queue accounting")
    priorities=[];seen=set();count=0;seen_shards=set()
    for row in rows:
        shard=row.get("shard_id") if isinstance(row,dict) else None
        items=row.get("issuer_reasons") if isinstance(row,dict) else None
        if (not isinstance(shard,str) or not re.fullmatch(r"shard_[0-9]{4}",shard)
            or shard in seen_shards or not isinstance(items,list)
            or not 1<=len(items)<=8 or row.get("issuer_gap_count")!=len(items)):
            raise ValueError("invalid P2 shard gap source")
        seen_shards.add(shard)
        shard_index=int(shard[-4:])
        for item in items:
            count+=1
            code=item.get("issuer") if isinstance(item,dict) else None
            diag=item.get("original_gap_diagnostic") if isinstance(item,dict) else None
            reason=item.get("reason") if isinstance(item,dict) else None
            if (not isinstance(code,str) or not CODE.fullmatch(code)
                or code in seen or reason not in (
                    "INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS",
                    "MISSING_EXACT_ASOF_CLOSE","VENDOR_NOT_TRADABLE_ASOF",
                    "PRIOR_VOLUME_UNAVAILABLE")
                or not isinstance(diag,dict)
                or diag.get("historical_PIT_verified") is not False
                or diag.get("vendor_calendar_independently_verified") is not False
                or diag.get("repair_approved") is not False
                or not isinstance(diag.get("original_csv_sha256"),str)
                or not SHA.fullmatch(diag["original_csv_sha256"])):
                raise ValueError("invalid P2 original gap proof")
            seen.add(code)
            if code not in by_issuer:
                # A later P2 coverage update can be ahead of the P3 upstream
                # snapshot; no target until the source P3 queue catches up.
                continue
            p3=by_issuer[code]
            if (p3["sources"]!={diag["original_csv_sha256"]}
                or p3["shards"]!={shard_index}):
                raise ValueError("P2 original SHA/shard contradicts P3 verified P1")
            if (reason=="INSUFFICIENT_CONTIGUOUS_TRADABLE_BARS"
                and diag.get("category")=="VENDOR_SUSPENDED_IN_LAST_21_ROWS"
                and type(diag.get("last_21_vendor_rows_suspended")) is int
                and diag["last_21_vendor_rows_suspended"]>0):
                priorities.append(code)
    if count!=coverage["issuer_evidence_gap_count"]:
        raise ValueError("P2 gap issuer count mismatch")
    return priorities


def checked_archive_visit_hint(hint,source_epoch,known_issuers):
    """History is a scheduling hint, never independently certified PDF proof."""
    if hint is None:
        return None,{},{}
    if (not isinstance(hint,dict)
        or hint.get("phase")!="P3_ARCHIVED_RESEARCH_VISIT_HINT_NOT_OFFICIAL_EVIDENCE"
        or hint.get("source_roster_sha256")!=source_epoch
        or hint.get("trade_gate")!="BLOCKED"
        or hint.get("historical_PIT_verified") is not False
        or hint.get("official_history_search_exhaustive") is not False
        or hint.get("source_originals_fully_replayed_in_this_hint") is not False
        or hint.get("orders")!=[]
        or hint.get("executable_candidates")!=[]):
        raise ValueError("unsafe archived research visit hint")
    visits=hint.get("issuer_visit_counts")
    originals=hint.get("issuer_original_retrieval_counts")
    if (not isinstance(visits,dict) or not isinstance(originals,dict)
        or len(visits)>10000 or len(originals)>10000
        or type(hint.get("matching_archive_run_manifests")) is not int
        or not 0<=hint["matching_archive_run_manifests"]<=1500):
        raise ValueError("invalid prior issuer visit counts")
    for code,count in list(visits.items())+list(originals.items()):
        if (not isinstance(code,str) or not CODE.fullmatch(code)
            or type(count) is not int or not 0<=count<=1500):
            raise ValueError("corrupted archived visit hint")
    if (not set(originals).issubset(visits)
        or any(count>visits[code] for code,count in originals.items())
        or hint.get("total_archived_issuer_attempts")!=sum(visits.values())
        or hint.get("distinct_attempted_issuers")!=len(visits)):
        raise ValueError("prior research visits not reconciled")
    # Same-epoch archive can be ahead of a lagged P3 upstream artifact:
    # such unmatched codes must never become selection candidates.
    return hint,{c:visits[c] for c in known_issuers if c in visits},{
        c:originals[c] for c in known_issuers if c in originals}


def plan(full_queue,limit=3,p2_coverage=None,rotation_index=None,visited_hint=None):
    q=full_queue
    if rotation_index is not None and (type(rotation_index) is not int or not 1<=rotation_index<=1000000000):
        raise ValueError("invalid bounded P3 workflow rotation index")
    if (q.get("phase")!="P3_ALL_COMPLETED_P1_OFFICIAL_PIT_WORKLIST"
        or q.get("trade_gate")!="BLOCKED"
        or q.get("historical_PIT_verified") is not False
        or q.get("independently_verified_official_PIT_cells")!=0
        or q.get("full_historical_status_coverage_authenticated") is not False
        or q.get("latest_quote_freshness_authenticated") is not False):
        raise ValueError("unsafe full P1 official-source worklist")
    count=q.get("completed_issuers_replayed");shards=q.get("completed_shards_replayed")
    tasks=q.get("official_evidence_tasks")
    if (type(count)!=int or not 1<=count<=10000 or
        type(shards)!=int or not 1<=shards<=10000 or
        type(limit)!=int or limit!=3 or not isinstance(tasks,list)
        or len(tasks)!=q.get("required_official_evidence_cells")):
        raise ValueError("invalid full-archive queue accounting")
    by_issuer=defaultdict(lambda:{"days":set(),"kinds":set(),"shards":set(),"sources":set(),
                                   "status_by_day":{},"transition_days":set(),"date_kinds":defaultdict(set)})
    has_vendor_status=q.get("vendor_suspended_context_included") is True
    seen=set()
    for item in tasks:
        code=item.get("issuer");day=item.get("decision_day");kind=item.get("status_kind")
        digest=item.get("vendor_csv_sha256")
        key=(code,day,kind)
        if (not isinstance(code,str) or not CODE.fullmatch(code)
            or not isinstance(day,str) or not isinstance(kind,str) or kind not in KINDS
            or not isinstance(digest,str) or not SHA.fullmatch(digest)
            or item.get("status")!="OFFICIAL_PIT_EVIDENCE_REQUIRED"
            or item.get("historical_asof_verified") is not False
            or item.get("official_publisher_authenticated") is not False
            or item.get("whole_day_state_coverage_authenticated") is not False
            or item.get("official_original_sha256") is not None
            or item.get("official_first_publication_utc") is not None
            or key in seen):
            raise ValueError("unsupported or duplicated historical PIT evidence claim")
        seen.add(key)
        try:
            decision=date.fromisoformat(day)
            cutoff=date.fromisoformat(q["frozen_vendor_query_end"])
        except (KeyError,ValueError,TypeError) as exc:raise ValueError("invalid historical date") from exc
        if decision>cutoff:raise ValueError("decision date after frozen source")
        d=by_issuer[code];d["days"].add(day);d["kinds"].add(kind)
        d["shards"].add(item.get("source_shard"));d["sources"].add(digest)
        d["date_kinds"][day].add(kind)
        if has_vendor_status:
            status=item.get("vendor_tradestatus_observed")
            if status not in ("0","1"):
                raise ValueError("missing or invalid vendor historical trading status")
            previous=d["status_by_day"].setdefault(day,status)
            if previous!=status:
                raise ValueError("inconsistent vendor trade status across evidence kinds")
            if item.get("vendor_possible_halt_transition_observed") is True:
                if status!="0":raise ValueError("transition must have vendor nontrading marker")
                d["transition_days"].add(day)
    if len(by_issuer)!=count:raise ValueError("missing P1 source issuer")
    for issuer,d in by_issuer.items():
        if len(d["shards"])!=1 or len(d["sources"])!=1 or d["kinds"]!=KINDS:
            raise ValueError("inconsistent original P1 issuer evidence cells")
        if any(kinds!=KINDS for kinds in d["date_kinds"].values()):
            raise ValueError("missing date-specific official evidence category")
        if len([x for x in tasks if x["issuer"]==issuer])!=len(d["days"])*4:
            raise ValueError("issuer evidence count mismatch")
    issuers=sorted(by_issuer,key=lambda c:(next(iter(by_issuer[c]["shards"])),c))
    visited,visit_counts,original_counts=checked_archive_visit_hint(
        visited_hint,q["roster_source_sha256"],set(issuers))
    # Legacy offline callers retain shard-based rotation. Real workflow runs
    # use a positive run number so a frozen P1 count does not pin the same
    # three official-source suspects forever.
    cycle=(rotation_index-1) if rotation_index is not None else max(0,shards//4-1)
    start=(cycle*limit)%count
    prioritized=verified_p2_vendor_priority(p2_coverage,q,by_issuer)
    # Research coverage: with archive history, reserve ONE bounded slot for
    # a source-SHA matched P2 halt suspect and use the other TWO for the
    # lowest-visit issuers across ALL P1-audited source issuers. Without
    # archive history the earlier bounded deterministic rotation is retained.
    p2_selected=[]
    if visited is not None:
        rotated=[]
        if prioritized:
            offset=(cycle*limit)%len(prioritized)
            rotated=[prioritized[(offset+i)%len(prioritized)]
                     for i in range(len(prioritized))]
            rotated.sort(key=lambda code:visit_counts.get(code,0))
        p2_selected=rotated[:1]
        # Break equal-history ties by the run rotation, not by a static
        # list that repeatedly privileges early roster entries.
        all_rotated=[issuers[(start+i)%count] for i in range(count)]
        all_rotated.sort(key=lambda code:visit_counts.get(code,0))
        picks=list(p2_selected)
        for issuer in all_rotated:
            if issuer not in picks:picks.append(issuer)
            if len(picks)==limit:break
    else:
        if prioritized:
            offset=(cycle*limit)%len(prioritized)
            rotated=[prioritized[(offset+i)%len(prioritized)]
                     for i in range(len(prioritized))]
            p2_selected=rotated[:limit]
        if has_vendor_status:
            # Vendor flags are research observations, never PIT evidence.
            suspended=[c for c in issuers if "0" in by_issuer[c]["status_by_day"].values()]
            normal=[c for c in issuers if c not in set(suspended)]
            picks=list(p2_selected)
            if suspended and len(picks)<limit:
                offset=(cycle*limit)%len(suspended)
                for i in range(len(suspended)):
                    issuer=suspended[(offset+i)%len(suspended)]
                    if issuer not in picks:picks.append(issuer)
                    if len(picks)==limit:break
            if len(picks)<limit and normal:
                offset=start%len(normal)
                for i in range(len(normal)):
                    issuer=normal[(offset+i)%len(normal)]
                    if issuer not in picks:picks.append(issuer)
                    if len(picks)==limit:break
        else:
            picks=list(p2_selected)
            for i in range(count):
                issuer=issuers[(start+i)%count]
                if issuer not in picks:picks.append(issuer)
                if len(picks)==limit:break
    if not picks or len(picks)!=min(limit,count) or len(set(picks))!=len(picks):
        raise ValueError("P3 bounded visit-aware target selection cannot reconcile")

    targets=[{"issuer":issuer,"observed_decision_dates":sorted(by_issuer[issuer]["days"]),
              "vendor_suspended_research_days":sorted(day for day,status in by_issuer[issuer]["status_by_day"].items() if status=="0"),
              "vendor_halt_transition_research_days":sorted(by_issuer[issuer]["transition_days"]),
              "target_selection_basis":("P2_SHA_CHECKED_RECENT_VENDOR_SUSPENSION_NOT_OFFICIAL" if issuer in p2_selected else "ARCHIVED_LEAST_VISITED_P1_SOURCE_RESEARCH_ONLY" if visited is not None else "VENDOR_NONTRADING_OBSERVED_NOT_OFFICIAL" if "0" in by_issuer[issuer]["status_by_day"].values() else "FROZEN_SHARD_ROTATION"),
              "cells_to_research":len(by_issuer[issuer]["days"])*4,
              "prior_archived_scout_attempts":visit_counts.get(issuer,0) if visited is not None else None,
              "prior_archived_pdf_retrievals":original_counts.get(issuer,0) if visited is not None else None,
              "original_official_url":None,"original_publication_time":None,
              "research_state":"SOURCE_DISCOVERY_REQUIRED_NOT_CERTIFIED"} for issuer in picks]
    return {"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE",
            "source_roster_sha256":q["roster_source_sha256"],
            "full_source_issuers":count,"full_source_pending_cells":len(tasks),
            "rotating_start_index":start,
            "rotation_basis":("P3_WORKFLOW_RUN_NUMBER" if rotation_index is not None else "P1_COMPLETED_SHARDS_LEGACY"),
            "rotation_index":rotation_index,
            "vendor_suspended_context_available":has_vendor_status,
            "vendor_nontrading_research_targets":sum(bool(t["vendor_suspended_research_days"]) for t in targets),
            "p2_original_sha_priority_targets":len(p2_selected),
            "full_p1_coverage_slots":len(picks)-len(p2_selected) if visited is not None else 0,
            "newly_unvisited_p1_targets":sum(visit_counts.get(c,0)==0 for c in picks) if visited is not None else None,
            "p2_hint_is_official_evidence":False,
            "archive_visit_hint_present":visited is not None,
            "archive_visit_hint_is_official_proof":False,
            "archived_same_epoch_runs_checked":visited["matching_archive_run_manifests"] if visited is not None else None,
            "unmatched_issuer_kind_targets":len(targets)*4,
            "unmatched_cells":sum(t["cells_to_research"] for t in targets),
            "targets":targets,"official_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True);p.add_argument("--out",required=True)
    p.add_argument("--p2-feature-coverage")
    p.add_argument("--archive-visit-hint")
    p.add_argument("--rotation-index",type=int)
    a=p.parse_args()
    hint=json.loads(Path(a.p2_feature_coverage).read_text()) if a.p2_feature_coverage else None
    history=json.loads(Path(a.archive_visit_hint).read_text()) if a.archive_visit_hint else None
    q=plan(json.loads(Path(a.queue).read_text()),p2_coverage=hint,
           rotation_index=a.rotation_index,visited_hint=history)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in q.items() if k!="targets"}))
if __name__=="__main__":main()
