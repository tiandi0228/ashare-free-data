"""Replay all nineteen official originals and retain raw index metadata without PIT claims."""
import argparse,json,zipfile,hashlib,copy
from pathlib import Path
from collector.p3_unified_ledger import verified_pdf,index_tasks
from collector.p3_final_cninfo_index import select
from collector.p3_next_originals import safe
PIN="761b9358168d3fd14ef44537a980b702361f8a332089b1dc0f0eecad75bcd3ea"
def sha(b):return hashlib.sha256(b).hexdigest()
def merge(base,last,final):
    for x in (base,last,final):safe(x)
    by={r["issuer"]:copy.deepcopy(r) for r in base["records"]}
    if len(by)!=19 or len(base["records"])!=19 or base["original_issuers_verified"]!=15:raise ValueError("bad baseline")
    if last["total_original_issuers_verified"]!=18 or final["total_original_issuers_verified"]!=19 or final["remaining_original_gaps"]!=[]:raise ValueError("incomplete originals")
    additions=last["records"]+[final["record"]]
    if len(additions)!=4 or {r["issuer"] for r in additions}!=set(base["remaining_original_gaps"]):raise ValueError("wrong additions")
    for r in additions:
        t=by[r["issuer"]]
        if t["official_original_verified"] is not False or r["official_original_verified"] is not True or r["extension_sha256"]!=t["extension_sha256"]:raise ValueError("wrong provenance")
        if any(r.get(k) is not False for k in ("official_certified","first_publication_verified","full_interval_verified")):raise ValueError("unexpected certification")
        t.update(r,pdf_sha256=r["source_sha256"],status="ORIGINAL_BYTES_VERIFIED",eligible_for_trading=False)
    if any(r["official_original_verified"] is not True or r["official_certified"] is not False or r["first_publication_verified"] is not False for r in by.values()):raise ValueError("unsafe record")
    return by
def run(archive,queue,root):
    tasks=index_tasks(queue)
    if sha(archive.read_bytes())!=PIN:raise ValueError("archive mismatch")
    root.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError("duplicate archive members")
        if json.loads(z.read("p3-refresh-gap-triage.json"))!=queue:raise ValueError("queue changed")
        names=("p3-unified-ledger.json","p3-last-originals.json","p3-final-cninfo-index.json")
        reports=[json.loads(z.read(n)) for n in names]
        by=merge(*reports)
        if set(by)!=set(tasks):raise ValueError("wrong scope")
        final=reports[2]["record"]
        meta=z.read("p3-final-cninfo-index/cninfo-index.json")
        if sha(meta)!=final["index_sha256"]:raise ValueError("index hash mismatch")
        row,url,stamp=select(meta)
        if (url,stamp,row["announcementId"],row["announcementTime"])!=(final["url"],final["index_timestamp_beijing"],final["index_announcement_id"],final["index_timestamp_ms"]):raise ValueError("index mismatch")
        (root/"cninfo-index.json").write_bytes(meta)
        additions={r["issuer"] for r in reports[1]["records"]}
        for code,r in by.items():
            if r["extension_sha256"]!=tasks[code]["extension_sha256"]:raise ValueError("vendor hash mismatch")
            filename=code+".pdf"
            if r["file"]!=filename:raise ValueError("wrong filename")
            folder="p3-final-cninfo-index" if code==final["issuer"] else "p3-last-originals" if code in additions else "p3-unified-originals"
            raw=z.read(folder+"/"+filename);verified_pdf(raw,r["pdf_sha256"]);(root/filename).write_bytes(raw)
            r["source_archive_member"]=folder+"/"+filename
    return dict(asof=queue["asof"],source_archive_sha256=PIN,gap_issuers=19,original_issuers_verified=19,remaining_original_gaps=[],index_metadata_verified=1,index_timestamp_semantics_verified=False,issuer_network_calls=0,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=[by[c] for c in sorted(by)])
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("archive","queue","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(a.archive,json.loads(a.queue.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_COMPLETE_ORIGINAL_LEDGER:",json.dumps({k:v for k,v in r.items() if k!="records"}))
