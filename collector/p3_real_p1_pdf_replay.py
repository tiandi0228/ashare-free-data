"""Independently replay bounded real-P1 PDF originals, never promote historical PIT."""
import argparse,hashlib,json,re
from pathlib import Path
from collector.p3_real_target_pdf_capture import URL_RE,ISSUER_RE

def audit(root):
    root=Path(root)
    q=json.loads((root/"quality.json").read_text())
    if q.get("phase")!="P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE" or q.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid original capture receipt")
    rows=q.get("sources")
    if not isinstance(rows,list) or len(rows)!=q.get("attempted") or len(rows)>3:
        raise ValueError("invalid bounded source count")
    verified=0;seen=set()
    for row in rows:
        issuer=row.get("issuer");identifier=row.get("announcement_id")
        match=URL_RE.fullmatch(row.get("url",""))
        if (not isinstance(issuer,str) or not ISSUER_RE.fullmatch(issuer)
            or not match or identifier!=match.group(1)):
            raise ValueError("invalid source identity")
        key=(issuer,identifier)
        if key in seen:raise ValueError("duplicate original")
        seen.add(key)
        expected_name=issuer.replace(".","_")+"_"+identifier+".pdf"
        path=root/expected_name
        if row.get("original_bytes_verified") is True:
            if row.get("original_file")!=expected_name or not path.is_file():
                raise ValueError("missing original")
            raw=path.read_bytes()
            if not 3000<=len(raw)<=4000000 or not raw.startswith(b"%PDF-"):
                raise ValueError("invalid original bytes")
            if hashlib.sha256(raw).hexdigest()!=row.get("sha256"):
                raise ValueError("SHA mismatch")
            if not row.get("observed_at_utc"):raise ValueError("missing observation instant")
            verified+=1
        elif path.exists():
            raise ValueError("unreceipted original file")
        if row.get("historical_PIT_verified") is not False or row.get("historical_first_publication_authenticated") is not False:
            raise ValueError("unsupported PIT promotion")
    if verified!=q.get("retrieved"):raise ValueError("retrieval count differs from replay")
    return {"phase":"P3_REAL_P1_ORIGINAL_INDEPENDENT_REPLAY","attempted":len(rows),
            "independently_sha_verified":verified,"historical_PIT_eligible":0,
            "historical_first_publication_authenticated":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=audit(a.root)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
if __name__=="__main__":main()
