"""P3 source-index/PDF join: research evidence, never proof of first publication."""
import argparse,json,re
from pathlib import Path
from urllib.parse import urlparse

SHA=re.compile(r"[0-9a-f]{64}\Z")
def reconcile(index_rows,pdf_report):
    if pdf_report.get("trade_gate")!="BLOCKED" or pdf_report.get("historical_PIT_eligible")!=0:
        raise ValueError("unsafe PDF receipt")
    if not isinstance(index_rows,list):raise ValueError("index list missing")
    indexed={};seen=set()
    for row in index_rows:
        aid=str(row.get("announcement_id",""))
        if not aid.isdigit() or aid in seen:raise ValueError("missing or duplicate announcement ID")
        seen.add(aid)
        indexed[aid]=row
    linked=[];unmatched=[]
    for pdf in pdf_report.get("sources",[]):
        if not pdf.get("original_bytes_verified"):continue
        aid=str(pdf.get("announcement_id",""))
        if aid not in indexed:
            unmatched.append(pdf["source_id"]);continue
        idx=indexed[aid]
        if idx.get("issuer")!=pdf.get("issuer"):raise ValueError("issuer mismatch")
        if idx.get("original_url")!=pdf.get("url"):raise ValueError("URL identity mismatch")
        digest=pdf.get("sha256")
        if not isinstance(digest,str) or not SHA.fullmatch(digest):raise ValueError("invalid original PDF digest")
        url=urlparse(pdf["url"])
        if url.scheme!="https" or url.hostname not in ("static.cninfo.com.cn","static.sse.com.cn","big5.sse.com.cn"):
            raise ValueError("untrusted original URL")
        linked.append({"announcement_id":aid,"issuer":pdf["issuer"],"original_sha256":digest,
                       "index_timestamp_unverified":idx.get("published_at"),
                       "original_bytes_verified":True,
                       "first_publication_instant_authenticated":False,
                       "historical_issuer_day_PIT_certified":False})
    return {"phase":"P3_INDEX_TO_OFFICIAL_PDF_RECEIPT_JOIN","linked_count":len(linked),
            "unmatched_pdf_sources":unmatched,"links":linked,
            "authenticated_first_publication_count":0,
            "historical_PIT_eligible_count":0,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",required=True);p.add_argument("--pdf",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=reconcile(json.loads(Path(a.index).read_text()),json.loads(Path(a.pdf).read_text()))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="links"}))
if __name__=="__main__":main()
