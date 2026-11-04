"""Bounded rotating pages of real SHA-pinned archived P1 research CSVs.

Deterministic coverage page selection; never reports a full-market scan, PIT
status, tradable signal, order, or forward validation. Existing offline
P2 archived-original checks must independently replay every selected shard.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from collector.baostock_batch import END
from collector.p1_checkpoint import validate
from collector.p2_real_archive_features import observe

PAGE_SHARDS=16
PHASE="P2_PAGED_REAL_ARCHIVE_FEATURE_REPLAY"

def select_page(mapped,source_epoch,run_number,page=None,coverage=None):
    """Use verified existing durable coverage as a *hint*, never as source truth.

    Priority: most unobserved archived shards, then deterministic rotation.
    A frozen source's known as-of indicator gaps cannot be repaired simply by
    preferentially replaying the same original CSV forever. Continue checking
    every page in rotation. Invalid or cross-epoch hints are ignored.
    """
    pages=(len(mapped)+PAGE_SHARDS-1)//PAGE_SHARDS
    if page is not None:
        if type(page) is not int or not 0<=page<pages:
            raise ValueError("PAGE_OUT_OF_RANGE")
        return page,"EXPLICIT_PAGE"
    fallback=(run_number-1)%pages
    if not isinstance(coverage,dict) or coverage.get("source_epoch_sha256")!=source_epoch or (
        coverage.get("phase")!="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
        or coverage.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
        or coverage.get("trade_gate")!="BLOCKED"
        or coverage.get("historical_PIT_verified") is not False
        or coverage.get("coverage_certified_for_trading") is not False
        or coverage.get("orders")!=[]):
        return fallback,"NO_VALID_DURABLE_COVERAGE_ROTATION"
    known={f"shard_{i:04d}" for i,_ in mapped}
    unseen=coverage.get("unobserved_shard_ids")
    gaps=coverage.get("gap_shard_ids")
    if (not isinstance(unseen,list) or not isinstance(gaps,list)
        or any(not isinstance(i,str) for i in unseen+gaps)
        or len(set(unseen))!=len(unseen)
        or len(set(gaps))!=len(gaps)
        or not set(unseen).issubset(known)
        or not set(gaps).issubset(known)
        or set(unseen)&set(gaps)):
        return fallback,"INVALID_COVERAGE_HINT_ROTATION"
    if unseen:
        scores=[sum(f"shard_{i:04d}" in unseen
                    for i,_ in mapped[p*PAGE_SHARDS:(p+1)*PAGE_SHARDS])
                for p in range(pages)]
        best=max(scores)
        return next(p for p in range(pages) if scores[p]==best),"PRIORITIZE_UNOBSERVED_SHARDS"
    if gaps:
        return fallback,"KNOWN_ASOF_GAPS_ROTATION"
    return fallback,"ALL_ARCHIVED_SHARDS_OBSERVED_ROTATION"


def select_catchup_shards(mapped,source_epoch,coverage):
    """Use durable coverage only as a hint; replay selected originals afresh.

    Include new same-epoch archived shards not present in the previous summary.
    Invalid or cross-epoch hints fall back to the normal page rotation.
    """
    if (not isinstance(coverage,dict)
            or coverage.get("phase")!="P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE"
            or coverage.get("status")!="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
            or coverage.get("source_epoch_sha256")!=source_epoch
            or coverage.get("trade_gate")!="BLOCKED"
            or coverage.get("historical_PIT_verified") is not False
            or coverage.get("full_market_universe_verified") is not False
            or coverage.get("coverage_certified_for_trading") is not False
            or coverage.get("orders")!=[]
            or coverage.get("executable_candidates")!=[]
            or coverage.get("actionable_buy_signals")!=[]):
        return []
    observed=coverage.get("observed_shard_ids")
    unseen=coverage.get("unobserved_shard_ids")
    gaps=coverage.get("gap_shard_ids")
    if (not all(isinstance(v,list) for v in (observed,unseen,gaps))
            or any(not isinstance(s,str) for s in observed+unseen+gaps)
            or any(len(set(v))!=len(v) for v in (observed,unseen,gaps))
            or set(observed)&set(unseen)
            or not set(gaps).issubset(observed)
            or type(coverage.get("archived_original_shards")) is not int
            or coverage["archived_original_shards"]!=len(observed)+len(unseen)
            or coverage.get("observed_archived_shards")!=len(observed)
            or coverage.get("unobserved_archived_shards")!=len(unseen)):
        return []
    known={f"shard_{i:04d}" for i,_ in mapped}
    if not (set(observed)|set(unseen)).issubset(known):
        return []
    pending=[(i,source) for i,source in mapped
             if f"shard_{i:04d}" not in observed]
    return pending[:PAGE_SHARDS]

def run(archive_root,checkpoint_root,out,page=None,run_number=1,coverage_summary=None):
    root=Path(archive_root)
    output=Path(out)
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "historical_PIT_verified":False,"full_market_universe_verified":False}
    def reject(reason):
        result=dict(base,reason=reason)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        return result
    try:
        if type(run_number) is not int or run_number<1:
            return reject("INVALID_RUN_NUMBER")
        if page is not None and (type(page) is not int or page<0):
            return reject("INVALID_PAGE")
        commit=subprocess.check_output(
            ["git","-C",str(root),"rev-parse","HEAD"],text=True,timeout=15).strip()
        if len(commit)!=40 or any(ch not in "0123456789abcdef" for ch in commit):
            return reject("INVALID_ARCHIVE_COMMIT")
        candidates=[]
        for file in sorted(Path(checkpoint_root).glob("*.json")):
            checkpoint=json.loads(file.read_text())
            validate(checkpoint)
            if file.stem!=checkpoint["source_sha256"]:
                return reject("FROZEN_CHECKPOINT_SHA_MISMATCH")
            epoch=root/checkpoint["source_sha256"][:16]
            if (epoch/"archive_status.json").is_file():
                candidates.append((checkpoint["completed_shards"],
                                   checkpoint["source_sha256"],epoch,checkpoint))
        if not candidates:return reject("NO_CHECKPOINT_MATCHES_ARCHIVE_EPOCH")
        _,sha,epoch,ledger=max(candidates,key=lambda x:(x[0],x[1]))
        status=json.loads((epoch/"archive_status.json").read_text())
        if status.get("source_sha256")!=sha or status.get("trade_gate")!="BLOCKED":
            return reject("ARCHIVE_EPOCH_MISMATCH")
        source_shards=sorted(epoch.glob("shard_*/quality.json"))
        if not source_shards:return reject("NO_ARCHIVED_SHARDS")
        by_index={i["index"] for i in ledger["completed"]}
        mapped=[]
        for source in source_shards:
            label=source.parent.name
            if not(label.startswith("shard_") and len(label)==10 and label[6:].isdigit()):
                return reject("INVALID_SHARD_PATH")
            index=int(label[6:])
            if index not in by_index:
                return reject("ARCHIVED_SHARD_ABSENT_FROM_FROZEN_LEDGER")
            mapped.append((index,source))
        if len({x[0] for x in mapped})!=len(mapped):
            return reject("DUPLICATE_ARCHIVED_SHARDS")
        mapped.sort()
        pages=(len(mapped)+PAGE_SHARDS-1)//PAGE_SHARDS
        if page is not None and page>=pages:
            return reject("PAGE_OUT_OF_RANGE")
        catchup=(select_catchup_shards(mapped,sha,coverage_summary)
                 if page is None else [])
        if catchup:
            selection=catchup
            selection_method="PRIORITIZE_UNOBSERVED_ACROSS_PAGES"
            selected_page=next(pos//PAGE_SHARDS for pos,row in enumerate(mapped)
                               if row[0]==selection[0][0])
        else:
            selected_page,selection_method=select_page(
                mapped,sha,run_number,page,coverage_summary)
            selection=mapped[selected_page*PAGE_SHARDS:(selected_page+1)*PAGE_SHARDS]
        positions={index:pos//PAGE_SHARDS for pos,(index,_) in enumerate(mapped)}
        selected_page_indices=sorted({positions[index] for index,_ in selection})
        stage=output.parent/("p2_paged_input_"+commit[:12])/epoch.name
        if stage.exists():shutil.rmtree(stage)
        stage.mkdir(parents=True)
        for index,source in selection:
            shutil.copytree(source.parent,stage/source.parent.name)
        result=observe(stage.parent,END,max_issuers=PAGE_SHARDS*8)
        if (result.get("status")!="REAL_ARCHIVED_BAR_FEATURES_RESEARCH_ONLY"
                or result.get("trade_gate")!="BLOCKED"
                or result.get("orders")!=[]
                or result.get("actionable_buy_signals")!=[]
                or result.get("historical_PIT_verified") is not False
                or result.get("full_market_universe_verified") is not False
                or result.get("scoped_verified_issuers",0)>PAGE_SHARDS*8):
            return reject("PAGED_ORIGINAL_REPLAY_REJECTED")
        report=dict(base,status="PAGED_REAL_ARCHIVE_RESEARCH_ONLY",
            source_epoch_sha256=sha,archive_commit_sha=commit,
            asof_completed_day=END,page_index=selected_page,
            total_pages=pages,selection_method=selection_method,
            selected_page_indices=selected_page_indices,
            archived_shards_in_selected_epoch=len(mapped),
            checkpoint_completed_shards=ledger["completed_shards"],
            checkpoint_total_shards=ledger["shard_count"],
            selected_shards=[f"shard_{i:04d}" for i,_ in selection],
            processed_shards=len(selection),
            scoped_verified_issuers=result["scoped_verified_issuers"],
            computed_feature_issuers=result["feature_issuers"],
            missing_feature_evidence_issuers=result["insufficient_evidence_issuers"],
            features=result["features"],
            evidence_gaps=result["evidence_gaps"],
            reasons=[
                "BOUNDED_ARCHIVED_SHARD_SAMPLE_NOT_ALL_MARKET",
                "RESEARCH_ARCHIVE_ORIGINALS_NOT_OFFICIAL_PIT",
                "NO_SOURCE_CERTIFIED_SECTOR_CLASSIFICATION",
                "NOT_AN_EXECUTABLE_STRATEGY_OR_RETURN_BACKTEST",
            ])
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        return report
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        return reject("SOURCE_ARCHIVE_OR_CHECKPOINT_IO_FAILURE")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True)
    p.add_argument("--checkpoints",default="evidence/checkpoints")
    p.add_argument("--out",required=True)
    p.add_argument("--page",type=int)
    p.add_argument("--run-number",type=int,default=1)
    p.add_argument("--coverage-summary")
    a=p.parse_args()
    try:
        coverage=json.loads(Path(a.coverage_summary).read_text()) if a.coverage_summary else None
    except (OSError,ValueError,UnicodeError):coverage=None
    result=run(a.archive_root,a.checkpoints,a.out,a.page,a.run_number,coverage)
    print(json.dumps({k:result.get(k) for k in (
        "status","reason","page_index","selection_method","total_pages",
        "archived_shards_in_selected_epoch","processed_shards",
        "scoped_verified_issuers","computed_feature_issuers","trade_gate")}))
    if result["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
