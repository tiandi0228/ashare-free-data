"""Bridge two pinned official originals to current gap queue; retrospective only."""
import argparse,hashlib,json,zipfile,subprocess,re
from pathlib import Path
from datetime import date
PIN="29c314f023379729e5308b805a0ecd35188eccbdaeed4046387b7a2e1d35981d"
SOURCES={
"sz.002717":("9c2f3777bf177f750d12ad4151884e8eaed4c87a26111ff93ea1fbc22c1b4376","9de8cfc19b8fd000492c985fd09ddc7ff7ef50aa92e7aa9e02f6ab775e352ef4",("终止上市事先告知书","2026年10月13日","停牌"),"HALTED_PENDING_DELIST_DECISION"),
"sz.002731":("26788d351ebfd99bd32b4df65aeaa00f2b528cb5e975ad40b420106a78daaac3","76f5c3274f4ff77ee0567af02c8ce340e459d4a3251dab022b0159d0d6d0bcf2",("2026年11月12日","2026年11月13日","摘牌"),"DELISTED_RETROSPECTIVE")}
def sha(b):return hashlib.sha256(b).hexdigest()
def classify(task):
    code=task["issuer"]
    if code=="sz.002717" and len(task["vendor_nontradable_days"])==26 and not task["missing_expected_sessions"] and task["trailing_tradable_observations"]==0:return SOURCES[code][3]
    if code=="sz.002731" and task["missing_expected_sessions"]==["2026-11-13","2026-11-16","2026-11-17","2026-11-18","2026-11-19","2026-11-20","2026-11-23","2026-11-24","2026-11-25"] and task["trailing_tradable_observations"]==15:return SOURCES[code][3]
    raise ValueError("notice and vendor interval mismatch")
def run(archive,queue,root):
    if sha(archive.read_bytes())!=PIN or queue["source_artifact_sha256"]!=PIN or queue["asof"]!="2026-11-25" or queue["trade_gate"]!="BLOCKED" or queue["orders"]!=[] or queue["executable_candidates"]!=[] or queue["official_certified"]!=0 or queue["historical_PIT_verified"] is not False:raise ValueError("unsafe scope")
    tasks={t["issuer"]:t for t in queue["tasks"]}
    if len(tasks)!=19 or len(queue["tasks"])!=19:raise ValueError("wrong gap scope")
    root.mkdir(parents=True,exist_ok=True)
    records=[]
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError("duplicate archive members")
        for code,(pdfsha,csvsha,tokens,status) in SOURCES.items():
            t=tasks[code]
            if t["extension_sha256"]!=csvsha or sha(z.read(t["source_member"]))!=csvsha:raise ValueError("CSV mismatch")
            raw=z.read("p2-residual-risk/"+code+".pdf")
            if sha(raw)!=pdfsha or not raw.startswith(b"%PDF-"):raise ValueError("PDF mismatch")
            p=root/(code+".pdf");p.write_bytes(raw)
            text=re.sub(r"\s+","",subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=20))
            if code[3:] not in text or not all(x in text for x in tokens):raise ValueError("notice identity mismatch")
            if classify(t)!=status:raise ValueError("classification mismatch")
            records.append(dict(issuer=code,status=status,original_pdf_sha256=pdfsha,extension_sha256=csvsha,official_first_publication_verified=False,official_certified=False,eligible_for_trading=False))
    return dict(asof=queue["asof"],gap_issuers=len(tasks),retrospective_notice_supported=len(records),ordinary_halt_queue_remaining=len(tasks)-len(records),delisted_missing_sessions=9,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("artifact","queue","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(a.artifact,json.loads(a.queue.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_RESIDUAL_BRIDGE:",json.dumps(r))
