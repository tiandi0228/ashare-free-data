"""Build a bounded P3 official-state worklist from genuinely P2-checked P1 originals.
Does NOT claim that an unobserved exchange notice proves the absence of risk.
"""
import argparse,csv,json
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
    for item in receipt["details"]:
        code=item["code"]
        codes.append(code)
        rows=list(csv.DictReader((part/(code.replace(".","_")+".csv")).read_text(encoding="utf-8-sig").splitlines()))
        dates={r["date"] for r in rows if r["tradestatus"]=="1"}
        available=dates if available is None else available & dates
    days=sorted(available or [])[-3:]
    if not codes or not days or len(codes)>8:raise ValueError("no bounded common source observations")
    report=audit_coverage(codes,days,[])
    return {"phase":"P3_P1_OBSERVED_WORKLIST","source_sha256":plan["source_sha256"],
            "source_shard_index":index,"issuer_codes":sorted(codes),
            "observed_vendor_dates":days,"status_kinds":["listing","st","halt","delisting"],
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
    d.write_text(json.dumps(q,indent=2)+"\\n")
    print(json.dumps(q))
if __name__=="__main__":main()
