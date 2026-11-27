"""Capture issuer originals from exchange URLs; failures remain explicit, never PIT."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
SOURCES={
"sh.603595":("2026-11-25/603595_20261125_PDI4.pdf",("603595","2026-053","撤销其他风险警示","11月25日","11月26日")),
"sh.600185":("2026-11-26/600185_20261126_WKCR.pdf",("600185","重大资产重组","复牌","11月12日","11月26日")),
"sh.600567":("2026-11-26/600567_20261126_2HXN.pdf",("600567","重大事项","复牌","2026-075","11月26日")),
}
def verify(text,tokens):
    normalized=re.sub(r"\s+","",text).replace("－","-").replace("—","-")
    return all(t in normalized for t in tokens)
def run(leads,root):
    if leads["trade_gate"]!="BLOCKED" or leads["orders"]!=[] or leads["executable_candidates"]!=[] or leads["official_certified"]!=0 or leads["historical_PIT_verified"] is not False:raise ValueError("unsafe source")
    by={r["issuer"]:r for r in leads["records"]}
    if not set(SOURCES)<=set(by):raise ValueError("missing leads")
    root.mkdir(parents=True,exist_ok=True);records=[]
    for code,(suffix,tokens) in SOURCES.items():
        url="https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/"+suffix
        p=root/(code+".pdf")
        r=dict(issuer=code,url=url,official_original_verified=False,first_publication_verified=False,official_certified=False,resume_vendor_observed=False)
        try:
            subprocess.run(["curl","--fail","--silent","--show-error","--max-time","30","--max-filesize","5000000","--output",str(p),url],check=True)
            raw=p.read_bytes()
            if not raw.startswith(b"%PDF-") or len(raw)>5000000:raise ValueError("invalid PDF")
            text=subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=20)
            if not verify(text,tokens):raise ValueError("document identity mismatch")
            r.update(official_original_verified=True,source_sha256=hashlib.sha256(raw).hexdigest(),file=p.name,evidence_type="ISSUER_NOTICE_RETROSPECTIVE")
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            p.unlink(missing_ok=True);r["failure"]=type(e).__name__
        records.append(r)
    return dict(asof=leads["asof"],attempted=len(records),originals_verified=sum(r["official_original_verified"] for r in records),official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("leads","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.leads.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_EXCHANGE_ORIGINALS:",json.dumps(r))
