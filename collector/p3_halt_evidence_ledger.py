"""Reconcile the scoped halt evidence reports against the immutable priority queue."""
import argparse
import hashlib
import json
import re
from pathlib import Path

def load(path):
    return json.loads(path.read_bytes())

def reconcile(queue, root):
    inventory={}
    for task in queue["tasks"]:
        for target in task["targets"]:
            key=(task["code"],target["target_date"])
            if key in inventory: raise ValueError("duplicate queue key")
            inventory[key]=target
    if len(inventory)!=queue["target_days"]: raise ValueError("queue total mismatch")
    levels={}
    def safe(r):
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["officially_certified_halt_dates"]!=0:
            raise ValueError("unsafe report")
    def add(code,t,level):
        key=(code,t["target_date"])
        if key not in inventory or t["original_csv_sha256"]!=inventory[key]["original_csv_sha256"]:
            raise ValueError("unbound target")
        levels.setdefault(key,set()).add(level)
    def file_ok(folder,r):
        name=r["filename"]
        if Path(name).name!=name or not re.fullmatch(r"[0-9a-f]{64}",r["sha256"]):
            raise ValueError("unsafe file receipt")
        raw=(folder/name).read_bytes()
        if not raw.startswith(b"%PDF-") or hashlib.sha256(raw).hexdigest()!=r["sha256"]:
            raise ValueError("original SHA mismatch")
    safe(queue)
    folder=root/"p3_002931_notice_replay"
    r=load(folder/"report.json");safe(r)
    for i in r["intervals"]:
        for n in i["notices"]:file_ok(folder,n)
    for t in r["matched_targets"]:
        if sum(i["start"]<=t["target_date"]<i["resume"] for i in r["intervals"])!=1:
            raise ValueError("invalid interval")
        add(r["issuer"],t,"ORIGINAL_PAIR")
    folder=root/"p3_600491_notice_replay"
    r=load(folder/"report.json");safe(r)
    for n in r["receipts"]:
        if n["original_verified"] is True:
            file_ok(folder,n)
            if n["kind"]=="halt":
                for t in r["targets"]:
                    if t["target_date"]==n["day"]:add(r["issuer"],t,"OFFICIAL_SINGLE")
    folder=root/"p3_002969_retrospective_replay"
    r=load(folder/"report.json");safe(r)
    for n in r["receipts"]:
        if n["verified"] is True:file_ok(folder,n)
    if r["retrospective_matches"] and not any(n["day"]=="2026-02-11" and n["verified"] is True for n in r["receipts"]):
        raise ValueError("missing retrospective original")
    for t in r["retrospective_matches"]:add(r["issuer"],t,"OFFICIAL_RETROSPECTIVE")
    folder=root/"p3_two_issuer_notice_leads"
    r=load(folder/"report.json");safe(r)
    for n in r["receipts"]:
        if n["verified"] is True:
            file_ok(folder,n)
            if n["source"] not in ("MIRROR","CNINFO","EXCHANGE_REPORT_VIA_CNINFO"):
                raise ValueError("unknown source class")
            add(n["code"],n["target"],"MIRROR" if n["source"]=="MIRROR" else "OFFICIAL_SINGLE")
    rows=[]
    for (code,day),t in sorted(inventory.items()):
        tags=sorted(levels.get((code,day),set()))
        rows.append(dict(code=code,target_date=day,original_csv_sha256=t["original_csv_sha256"],
                         evidence_levels=tags,official_first_release_verified=False))
    return dict(target_days=len(rows),official_channel_supported_days=sum(any(x!="MIRROR" for x in r["evidence_levels"]) for r in rows),
                mirror_only_days=sum(r["evidence_levels"]==["MIRROR"] for r in rows),
                complete_original_pair_days=sum("ORIGINAL_PAIR" in r["evidence_levels"] for r in rows),
                no_matched_document_days=sum(not r["evidence_levels"] for r in rows),
                officially_certified_halt_dates=0,historical_PIT_verified=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[],rows=rows)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("queue",type=Path);p.add_argument("--root",type=Path,default=Path("."));p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=reconcile(load(a.queue),a.root)
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("HALT_EVIDENCE_LEDGER:",json.dumps({k:v for k,v in r.items() if k!="rows"},sort_keys=True))
