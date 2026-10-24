"""Build a bounded P3 official-state worklist from genuinely P2-checked P1 originals.
Does NOT claim that an unobserved exchange notice proves the absence of risk.
"""
import argparse,csv,json,hashlib
from pathlib import Path
from collector.p2_independent_bars import assess
from collector.p3_historical_evidence_coverage import audit_coverage

def worklist(root,plan,ledger):
    if ledger.get("source_sha256")!=plan.get("source_sha256") or ledger.get("trade_gate")!="BLOCKED":
        raise ValueError("different source epochs or unsafe ledger")
    completed=ledger.get("completed",[])
    if not completed:raise ValueError("no completed shard to assess")
    index=max(row["index"] for row in completed)
    part=Path(root)/plan["source_sha256"][:16]/f"shard_{index:04d}"
    receipt=assess(part)
    codes=[]
    available=None
    vendor_days={}
    source_hashes={}
    for item in receipt["details"]:
        code=item["code"]
        codes.append(code)
        raw=(part/(code.replace(".","_")+".csv")).read_bytes()
        source_hashes[code]=hashlib.sha256(raw).hexdigest()
        rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
        dates={r["date"] for r in rows}
        vendor_days[code]={r["date"]:r["tradestatus"] for r in rows}
        available=dates if available is None else available & dates
    common=sorted(available or [])
    risk_days=[d for d in common if any(vendor_days[c][d]!="1" for c in codes)]
    days=sorted((risk_days[-1:]+common[-2:]))
    days=sorted(set(days))[-3:]
    if not codes or not days or len(codes)>8:raise ValueError("no bounded common source observations")
    report=audit_coverage(codes,days,[])
    kinds=["listing","st","halt","delisting"]
    tasks=[{"code":code,"decision_date":day,"kind":kind,
            "vendor_source_csv_sha256":source_hashes[code],
            "official_original_sha256":None,
            "publication_instant_utc":None,
            "historical_asof_verified":False,
            "status":"OFFICIAL_EVIDENCE_REQUIRED"}
           for code in sorted(codes) for day in days for kind in kinds]
    if len(tasks)!=report["required_evidence_cells"]:
        raise ValueError("P3 task denominator mismatch")
    return {"phase":"P3_P1_OBSERVED_WORKLIST","source_sha256":plan["source_sha256"],
            "source_shard_index":index,"issuer_codes":sorted(codes),
            "vendor_original_csv_sha256_by_issuer":source_hashes,
            "observed_vendor_dates":days,"status_kinds":kinds,
            "vendor_status_observed_not_official":{c:{d:vendor_days[c][d] for d in days} for c in sorted(codes)},
            "official_evidence_tasks":tasks,
            "official_evidence_cells_required":report["required_evidence_cells"],
            "official_evidence_cells_verified":0,
            "official_evidence_cells_pending":report["required_evidence_cells"],
            "publisher_authenticated":False,"historical_PIT_verified":False,
            "full_market_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for arg in ("root","plan","ledger","out"):p.add_argument("--"+arg,required=True)
    x=p.parse_args()
    q=worklist(x.root,json.loads(Path(x.plan).read_text()),json.loads(Path(x.ledger).read_text()))
    d=Path(x.out);d.parent.mkdir(parents=True,exist_ok=True)
    d.write_text(json.dumps(q,indent=2)+"\n")
    print(json.dumps(q))
if __name__=="__main__":main()
