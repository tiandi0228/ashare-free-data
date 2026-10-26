"""Complete P1-to-P3 pending official-evidence queue, with SHA-bound issuer-days.

Unlike the bounded 8-issuer pilot, this worklist covers every *completed*
P1 shard in the immutable checkpoint, and verifies the original P2 receipts.
Neither vendor trading flags nor absent events prove official PIT status.
"""
import argparse,csv,hashlib,json
from pathlib import Path
from collector.p2_independent_bars import assess
from collector.baostock_batch import START,END
from collector.p3_historical_evidence_coverage import KINDS,CODE

def build(root,plan,ledger):
    if (plan.get("phase")!="P1_FRESH_VENDOR_SHARD_PLAN" or
        plan.get("trade_gate")!="BLOCKED" or
        plan.get("historical_PIT_verified") is not False or
        ledger.get("trade_gate")!="BLOCKED" or
        ledger.get("historical_PIT_verified") is not False or
        ledger.get("source_sha256")!=plan.get("source_sha256") or
        ledger.get("shard_count")!=plan.get("shard_count")):
        raise ValueError("unsafe or mismatched P1 source epoch")
    shards=plan.get("shards")
    if (not isinstance(shards,list) or len(shards)!=plan["shard_count"] or
        [s["index"] for s in shards]!=list(range(len(shards)))):
        raise ValueError("invalid P1 shard plan")
    completed=ledger.get("completed")
    if (not isinstance(completed,list) or not completed or
        len(completed)!=ledger.get("completed_shards") or
        sum(x["issuer_count"] for x in completed)!=ledger.get("completed_issuers")):
        raise ValueError("invalid completed source ledger")
    by_index={x["index"]:x for x in completed}
    if len(by_index)!=len(completed) or any(type(i)!=int or i<0 or i>=len(shards) for i in by_index):
        raise ValueError("duplicate or invalid source shard index")
    epoch=Path(root)/plan["source_sha256"][:16]
    marker=json.loads((epoch/"archive_status.json").read_text())
    archived=marker.get("archived_shards")
    if (marker.get("source_sha256")!=plan["source_sha256"] or
        marker.get("trade_gate")!="BLOCKED" or
        not isinstance(archived,list) or len(set(archived))!=len(archived) or
        set(archived)!=set(by_index)):
        raise ValueError("archive not identical to completed checkpoint")
    tasks=[];issuer_count=0;seen=set();source_first=None;source_last=None
    vendor_nontrading_issuer_count=0;vendor_nontrading_date_count=0
    for index in sorted(by_index):
        completed_shard=by_index[index];expected=shards[index]
        if (completed_shard.get("issuer_count")!=expected["count"] or
            completed_shard.get("manifest_sha256")!=expected["sha256"]):
            raise ValueError("checkpoint manifest mismatch")
        part=epoch/f"shard_{index:04d}"
        original=json.loads((part/"quality.json").read_text())
        digest=hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if digest!=completed_shard.get("receipt_sha256"):
            raise ValueError("checkpoint original receipt SHA mismatch")
        validated=assess(part)
        if validated["issuer_count"]!=expected["count"]:
            raise ValueError("P2 source coverage mismatch")
        for item in validated["details"]:
            code=item["code"]
            if code in seen or not CODE.fullmatch(code):
                raise ValueError("duplicate or invalid historical issuer")
            seen.add(code);issuer_count+=1
            raw=(part/(code.replace(".","_")+".csv")).read_bytes()
            source_sha=hashlib.sha256(raw).hexdigest()
            rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            if not rows or rows[0]["date"]<START or rows[-1]["date"]>END:
                raise ValueError("source date outside frozen vendor history range")
            source_first=min(source_first or rows[0]["date"],rows[0]["date"])
            source_last=max(source_last or rows[-1]["date"],rows[-1]["date"])
            selected={row["date"] for row in rows[-2:]}
            status_by_day={row["date"]:row["tradestatus"] for row in rows}
            risk_dates=[row["date"] for row in rows if row["tradestatus"]=="0"]
            if risk_dates:
                vendor_nontrading_issuer_count+=1
                vendor_nontrading_date_count+=1  # sampled last nontrading date only
            if risk_dates:
                selected.add(risk_dates[-1])
            for day in sorted(selected):
                for kind in KINDS:
                    tasks.append({"issuer":code,"decision_day":day,"status_kind":kind,
                                  "source_shard":index,"vendor_csv_sha256":source_sha,
                                  "vendor_tradestatus_observed":status_by_day[day],
                                  "official_original_sha256":None,
                                  "official_publisher_authenticated":False,
                                  "official_first_publication_utc":None,
                                  "whole_day_state_coverage_authenticated":False,
                                  "historical_asof_verified":False,
                                  "status":"OFFICIAL_PIT_EVIDENCE_REQUIRED"})
    if issuer_count!=ledger["completed_issuers"]:
        raise ValueError("missing completed issuer rows")
    expected=sum(len({r["decision_day"] for r in tasks if r["issuer"]==code}) for code in seen)*len(KINDS)
    if len(tasks)!=expected:raise ValueError("evidence cell denominator mismatch")
    return {"phase":"P3_ALL_COMPLETED_P1_OFFICIAL_PIT_WORKLIST",
            "roster_source_sha256":plan["source_sha256"],
            "completed_shards_replayed":len(by_index),
            "completed_issuers_replayed":issuer_count,
            "original_csv_replayed_by_P2":True,
            "sample_selection":"LAST_TWO_VENDOR_ROWS_PLUS_LATEST_VENDOR_NONTRADING_IF_PRESENT",
            "vendor_suspended_context_included":True,
            "issuers_with_vendor_nontrading_history":vendor_nontrading_issuer_count,
            "latest_vendor_nontrading_days_sampled":vendor_nontrading_date_count,
            "source_first_vendor_bar_day":source_first,
            "source_last_vendor_bar_day":source_last,
            "frozen_vendor_query_end":END,
            "latest_quote_freshness_authenticated":False,
            "required_official_evidence_cells":len(tasks),
            "independently_verified_official_PIT_cells":0,
            "official_evidence_tasks":tasks,
            "full_historical_status_coverage_authenticated":False,
            "historical_PIT_verified":False,
            "full_market_bars_certified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for name in ("root","plan","ledger","out"):p.add_argument("--"+name,required=True)
    x=p.parse_args()
    q=build(x.root,json.loads(Path(x.plan).read_text()),json.loads(Path(x.ledger).read_text()))
    out=Path(x.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in q.items() if k!="official_evidence_tasks"},ensure_ascii=False))
if __name__=="__main__":main()
