"""Read-only, source-epoch scoped history of P3 research visits.

Manifest presence means a past P3 scout ATTEMPTED an issuer; it never
establishes an authentic exchange event, a complete official-history search,
or the historical publication instant of any announcement.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

SHA=re.compile(r"[a-f0-9]{64}\Z")
ISSUER=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}\Z")
MAX_RUNS=1500
PHASE="P3_ARCHIVED_RESEARCH_VISIT_HINT_NOT_OFFICIAL_EVIDENCE"


def build(root,source_epoch):
    if not isinstance(source_epoch,str) or not SHA.fullmatch(source_epoch):
        raise ValueError("invalid target P1 source roster")
    paths=sorted((Path(root)/"runs").glob("*.json"))
    if not paths or len(paths)>MAX_RUNS:
        raise ValueError("unavailable or unbounded archived P3 run manifests")
    visits=Counter();retrieved=Counter();runs=0
    for path in paths:
        if (path.is_symlink() or not path.stem.isdigit()
            or int(path.stem)<1 or path.suffix!=".json"):
            raise ValueError("invalid P3 immutable run path")
        manifest=json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(manifest,dict)
            or manifest.get("phase")!="P3_PERSISTENT_ORIGINAL_PDF_RESEARCH_ARCHIVE"
            or manifest.get("run_id")!=int(path.stem)
            or manifest.get("trade_gate")!="BLOCKED"
            or manifest.get("orders")!=[]
            or manifest.get("historical_PIT_verified") is not False
            or any(manifest.get(k)!=0 for k in (
                "certified_first_publication_count",
                "certified_event_effective_day_count",
                "certified_historical_decision_state_count"))):
            raise ValueError("unsafe P3 archive manifest")
        epoch=manifest.get("source_roster_sha256")
        if not isinstance(epoch,str) or not SHA.fullmatch(epoch):
            raise ValueError("untrusted archived roster")
        receipts=manifest.get("source_pdf_receipts")
        if not isinstance(receipts,list) or len(receipts)>3:
            raise ValueError("invalid source research visit scope")
        if epoch!=source_epoch:
            continue
        runs+=1
        # New manifests independently record index attempts even when no
        # downloadable original existed. Legacy immutable manifests do not;
        # fall back to their narrower source-PDF receipt evidence.
        index_attempts=manifest.get("index_query_attempted_issuers_research_only")
        if index_attempts is not None:
            if not isinstance(index_attempts,list) or not 1<=len(index_attempts)<=3:
                raise ValueError("invalid P3 index attempt receipts")
            attempted=set()
            for item in index_attempts:
                issuer=item.get("issuer") if isinstance(item,dict) else None
                status=item.get("index_status_research_only") if isinstance(item,dict) else None
                if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
                    or issuer in attempted
                    or status not in ("INDEX_CANDIDATES_UNVERIFIED",
                                      "NO_INDEX_MATCH_NOT_NO_RISK",
                                      "INDEX_UNAVAILABLE_NOT_NO_RISK")
                    or item.get("historical_PIT_verified") is not False):
                    raise ValueError("invalid P3 archived index attempt")
                attempted.add(issuer);visits[issuer]+=1
        else:
            attempted=None
        seen=set()
        for row in receipts:
            if not isinstance(row,dict):
                raise ValueError("invalid historical source visit")
            issuer=row.get("issuer")
            if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
                or issuer in seen
                or row.get("historical_PIT_verified") is not False
                or row.get("historical_first_publication_authenticated") is not False
                or row.get("effective_date_authenticated") is not False
                or type(row.get("original_retrieved")) is not bool
                or (attempted is not None and issuer not in attempted)):
                raise ValueError("forged prior research visit")
            seen.add(issuer)
            if attempted is None:visits[issuer]+=1
            if row["original_retrieved"]:
                digest=row.get("pdf_sha256")
                if (not isinstance(digest,str) or not SHA.fullmatch(digest)
                    or row.get("archive_path")!=
                        f"pdf/{issuer.replace('.', '_')}/{row.get('announcement_id')}/{digest}.pdf"):
                    raise ValueError("prior original receipt not SHA anchored")
                retrieved[issuer]+=1
        if manifest.get("original_pdf_count")!=sum(
                row["original_retrieved"] for row in receipts):
            raise ValueError("archived PDF receipt count mismatch")
    return {
        "phase":PHASE,
        "source_roster_sha256":source_epoch,
        "matching_archive_run_manifests":runs,
        "total_archived_issuer_attempts":sum(visits.values()),
        "distinct_attempted_issuers":len(visits),
        "visit_count_includes_index_only_research_where_archived":True,
        "issuer_visit_counts":dict(sorted(visits.items())),
        "issuer_original_retrieval_counts":dict(sorted(retrieved.items())),
        "official_history_search_exhaustive":False,
        "historical_PIT_verified":False,
        "source_originals_fully_replayed_in_this_hint":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True)
    p.add_argument("--source-epoch",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=build(args.archive_root,args.source_epoch)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
        "matching_archive_run_manifests","total_archived_issuer_attempts",
        "distinct_attempted_issuers","historical_PIT_verified","trade_gate") }))


if __name__=="__main__":
    main()
