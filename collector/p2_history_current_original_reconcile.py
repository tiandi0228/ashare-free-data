"""Read-only current P2 original-replay comparison against historical, unverified counts.
Only the existing strict P2 ledger auditor may produce the live research counters.
"""
import argparse
import json
from pathlib import Path
from collector.p2_feature_coverage_ledger import summarize

def compare(checkpoint, history, replay=None):
    if not isinstance(checkpoint,dict) or checkpoint.get("phase")!="P1_ROSTER_SHARD_LEDGER":
        raise ValueError("invalid P1 checkpoint")
    source=checkpoint.get("source_sha256")
    total=checkpoint.get("shard_count")
    count=checkpoint.get("completed_shards")
    if not isinstance(source,str) or len(source)!=64 or any(c not in "0123456789abcdef" for c in source):
        raise ValueError("missing epoch identity")
    if type(total)!=int or type(count)!=int or total<=0 or not 0<=count<=total:
        raise ValueError("invalid checkpoint count")
    if not isinstance(history,list) or not history:raise ValueError("missing history")
    for row in history:
        if (not isinstance(row,dict) or row.get("kind")!="PREVIOUSLY_REPORTED_NOT_REPLAYED_THIS_RUN"
            or type(row.get("feature_complete_shards"))!=int or type(row.get("observed_shards"))!=int
            or not 0<=row["feature_complete_shards"]<=row["observed_shards"]<=total):
            raise ValueError("untrusted historical report")
    latest=history[-1]
    state="MISSING_CURRENT_ORIGINAL_REPLAY"
    current=None
    if replay is not None:
        if not isinstance(replay,dict) or replay.get("trade_gate")!="BLOCKED" or replay.get("orders")!=[] or replay.get("executable_candidates")!=[]:
            raise ValueError("unsafe replay result")
        if (replay.get("status")=="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED"
            and replay.get("source_epoch_sha256")==source
            and replay.get("historical_PIT_verified") is False
            and replay.get("coverage_certified_for_trading") is False):
            n=replay.get("feature_complete_shards")
            d=replay.get("observed_archived_shards")
            a=replay.get("archived_original_shards")
            if (type(n)!=int or type(d)!=int or type(a)!=int
                or not 0<=n<=d<=a<=count):
                raise ValueError("impossible replay counters")
            state="CURRENT_RESEARCH_ORIGINAL_REPLAY_UNCERTIFIED_FOR_TRADING"
            current={"feature_complete_shards":n,"observed_archived_shards":d,
                     "archived_original_shards":a,"source_epoch_sha256":source}
        elif replay.get("status")=="DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED":
            state="SOURCE_EPOCH_MISMATCH_OR_UNVERIFIED"
        else:
            state="CURRENT_REPLAY_REJECTED"
    return {
        "phase":"P2_HISTORICAL_VS_CURRENT_ORIGINAL_REPLAY",
        "status":state,
        "P1_checkpoint_shards":count, "P1_checkpoint_total":total,
        "P1_epoch_sha256":source,
        "historical_report_unreplayed":{"reported_day":latest.get("reported_day"),
            "feature_complete_shards":latest["feature_complete_shards"],
            "observed_shards":latest["observed_shards"]},
        "current_research_replay":current,
        "historical_minus_current_shards":None,
        "cross_epoch_counter_addition_allowed":False,
        "project_completion_pct":None,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED", "orders":[], "executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checkpoint",required=True,type=Path)
    p.add_argument("--history",required=True,type=Path)
    p.add_argument("--archive-epoch",type=Path)
    p.add_argument("--receipts",type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    checkpoint=json.loads(a.checkpoint.read_text())
    history=json.loads(a.history.read_text())
    if (a.archive_epoch is None)!=(a.receipts is None):
        raise SystemExit("archive and receipts must both be supplied")
    replay=None
    if a.archive_epoch is not None:
        if not a.archive_epoch.is_dir() or not a.receipts.is_dir():
            raise SystemExit("missing original archive or P2 receipts")
        reports=[json.loads(x.read_text()) for x in sorted(a.receipts.glob("*.json"))]
        replay=summarize(a.archive_epoch,checkpoint,reports)
    out=compare(checkpoint,history,replay)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out,ensure_ascii=False))
    if replay is not None and out["current_research_replay"] is None:
        raise SystemExit("independent P2 replay did not certify research counters")
if __name__=="__main__":
    main()
