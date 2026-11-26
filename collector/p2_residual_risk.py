"""Reconcile remaining P2 gaps with scoped issuer notices; no PIT certification."""
import argparse,hashlib,json,re,subprocess,csv
from pathlib import Path
from urllib.request import urlopen

SOURCES={
 "sz.002717":("https://static.cninfo.com.cn/finalpage/2026-10-17/1225609701.PDF",("终止上市事先告知书","2026年10月13日","停牌"),"HALTED_PENDING_DELIST_DECISION"),
 "sz.002731":("https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-11-13/f0878011-459d-4e1b-88c4-4f50876ae48f.PDF",("2026年11月12日","2026年11月13日","摘牌"),"DELISTED_RETROSPECTIVE"),
}
def classify(code,item,rows,notice_verified):
    if not notice_verified:return "UNVERIFIED_NOTICE"
    if code=="sz.002717" and len(rows)==26 and all(r["tradestatus"]=="0" for r in rows) and item["missing_expected_sessions"]==[]:
        return SOURCES[code][2]
    if code=="sz.002731" and rows[-1]["date"]=="2026-11-12" and item["missing_expected_sessions"] and item["missing_expected_sessions"][0]=="2026-11-13":
        return SOURCES[code][2]
    return "NOTICE_VENDOR_MISMATCH"
def run(root,out):
    report=json.loads((root/"report.json").read_bytes())
    if report["trade_gate"]!="BLOCKED" or report["orders"]!=[] or report["executable_candidates"]!=[]:
        raise ValueError("unsafe report")
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    for item in report["results"]:
        if item["recovered_at_new_cutoff"]:continue
        code=item["issuer"]
        r=dict(issuer=code,status="UNCLASSIFIED",official_first_publication_verified=False,eligible_for_trading=False)
        if code in SOURCES and item.get("status")=="VENDOR_EXTENSION_OBSERVED":
            url,phrases,_=SOURCES[code]
            p=root/item["filename"]
            if p.parent!=root or p.is_symlink():raise ValueError("unsafe CSV path")
            raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=item["extension_sha256"]:raise ValueError("CSV SHA mismatch")
            rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            r["source_csv_sha256"]=item["extension_sha256"]
            try:
                with urlopen(url,timeout=35) as response:
                    if response.geturl()!=url:raise ValueError("redirect")
                    pdf=response.read(8388609)
                if not pdf.startswith(b"%PDF-") or len(pdf)>8388608:raise ValueError("invalid PDF")
                dest=out/(code+".pdf");dest.write_bytes(pdf)
                text=re.sub(r"\s+","",subprocess.check_output(["pdftotext","-layout",str(dest),"-"],text=True,timeout=20))
                verified=code[3:] in text and all(x in text for x in phrases)
                r.update(url=url,pdf_sha256=hashlib.sha256(pdf).hexdigest(),notice_text_verified=verified,status=classify(code,item,rows,verified))
            except (ValueError,OSError,subprocess.SubprocessError) as e:r.update(status="UNVERIFIED_NOTICE",error=type(e).__name__)
        results.append(r)
    return dict(results=results,unrecovered=len(results),notice_explained=sum(r["status"] in ("HALTED_PENDING_DELIST_DECISION","DELISTED_RETROSPECTIVE") for r in results),historical_gaps_resolved=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=run(a.root,a.out);(a.out/"report.json").write_text(json.dumps(r,indent=2)+"\n")
    print("P2_RESIDUAL_RISK:",json.dumps(r,sort_keys=True))
