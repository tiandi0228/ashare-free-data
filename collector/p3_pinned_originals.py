"""Offline revalidation of four accepted original PDFs against the frozen gap ledger."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
PIN="b8aa4bf6db24285c6d71f66e50c5ab3d9a287e233cb8b5ea342244e3cc46585b"
DOCS={
"sz.002717":("p3-residual-originals/sz.002717.pdf","9c2f3777bf177f750d12ad4151884e8eaed4c87a26111ff93ea1fbc22c1b4376",("终止上市事先告知书","2026年10月13日","停牌")),
"sz.002731":("p3-residual-originals/sz.002731.pdf","26788d351ebfd99bd32b4df65aeaa00f2b528cb5e975ad40b420106a78daaac3",("2026年11月12日","2026年11月13日","摘牌")),
"sh.603595":("p3-exchange-originals/sh.603595.pdf","2935e3194e0abbd7e8fafb9a29bfc9265e729abc1116e1a0c4a5f9ece6e2c7dd",("2026-053","撤销其他风险警示","11月25日","11月26日")),
"sh.600185":("p3-initial-halt-originals/sh.600185-initial-halt.pdf","2a51cf41e5678a3d24697aff5252ac1fe4f95316ccc6a79529009ee60ae8070d",("2026-073","重大资产重组","停牌","2026年11月12日")),
}
def sha(b):return hashlib.sha256(b).hexdigest()
def safe(r):
    if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["historical_PIT_verified"] is not False or r["official_certified"]!=0 or r["asof"]!="2026-11-25":raise ValueError("unsafe source")
def check_bytes(raw,expected):
    if not raw.startswith(b"%PDF-") or len(raw)>5000000 or sha(raw)!=expected:raise ValueError("original PDF hash mismatch")
def run(archive,queue,root):
    safe(queue)
    if sha(archive.read_bytes())!=PIN:raise ValueError("archive hash mismatch")
    tasks={r["issuer"]:r for r in queue["tasks"]}
    if len(tasks)!=19 or len(queue["tasks"])!=19:raise ValueError("wrong scope")
    root.mkdir(parents=True,exist_ok=True);records=[]
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError("duplicate members")
        prior=json.loads(z.read("p3-refresh-gap-triage.json"));safe(prior)
        if prior!=queue:raise ValueError("frozen queue changed")
        reports=[json.loads(z.read(n)) for n in ("p3-residual-bridge.json","p3-exchange-originals.json","p3-initial-halt-original.json")]
        for r in reports:safe(r)
        known={r["issuer"]:r["original_pdf_sha256"] for r in reports[0]["records"]}
        known.update({r["issuer"]:r["source_sha256"] for r in reports[1]["records"] if r["official_original_verified"] is True})
        initial=reports[2]["record"]
        if initial["official_original_verified"] is not True:raise ValueError("initial halt not verified")
        known[initial["issuer"]]=initial["source_sha256"]
        if known!={c:d[1] for c,d in DOCS.items()}:raise ValueError("wrong known original scope")
        for code,(name,expected,tokens) in DOCS.items():
            raw=z.read(name);check_bytes(raw,expected)
            p=root/(code+".pdf");p.write_bytes(raw)
            text=re.sub(r"\s+","",subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=20)).replace("－","-").replace("—","-")
            if code[3:] not in text or not all(t in text for t in tokens):raise ValueError("identity mismatch")
            records.append(dict(issuer=code,pdf_sha256=expected,extension_sha256=tasks[code]["extension_sha256"],official_original_verified=True,first_publication_verified=False,full_interval_verified=False,official_certified=False))
    return dict(asof=queue["asof"],gap_issuers=19,original_issuers_verified=len(records),remaining_original_gaps=19-len(records),source_archive_sha256=PIN,provider_calls=0,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("archive","queue","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(a.archive,json.loads(a.queue.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_PINNED_ORIGINALS:",json.dumps(r))
