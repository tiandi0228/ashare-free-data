"""Bounded free official PDF capture with typed research cues, no PIT promotion."""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError

ALLOWED={"static.cninfo.com.cn","static.sse.com.cn","big5.sse.com.cn"}
class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        target=urlparse(newurl)
        if target.scheme!="https" or target.hostname not in ALLOWED:
            raise ValueError("redirect outside allowlisted HTTPS official hosts")
        return super().redirect_request(req,fp,code,msg,headers,newurl)

KINDS={"IPO_LISTING","DELIST_EFFECTIVE","DELIST_RISK_ISSUER_FORECAST","ST_CHANGE","TRADING_HALT","TRADING_RESUME"}
def capture(specs,out):
    if not isinstance(specs,list) or not 1<=len(specs)<=12:
        raise ValueError("source count outside 1..12")
    ids=set();out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
    for s in specs:
        sid=s["id"];url=s["url"];kind=s["kind"];code=s["issuer"]
        if (not re.fullmatch(r"[a-z0-9_]{3,60}",sid) or sid in ids or
            urlparse(url).scheme!="https" or urlparse(url).hostname not in ALLOWED or
            kind not in KINDS or not re.fullmatch(r"(sh|sz)[.][0-9]{6}",code)):
            raise ValueError("invalid original source specification")
        ids.add(sid)
        identifier=re.fullmatch(r"/finalpage/\\d{4}-\\d{2}-\\d{2}/(\\d+)\\.PDF",urlparse(url).path,re.I)
        if not identifier:raise ValueError("source URL lacks expected announcement ID")
        r={"source_id":sid,"issuer":code,"event_kind":kind,"url":url,
           "announcement_id":identifier.group(1),"announcement_id_origin":"PDF_URL_PATH_NOT_AUTHENTICATED_INDEX",
           "source_status":"UNVERIFIED","original_bytes_verified":False,
           "event_contents_certified":False,"PIT_publication_verified":False}
        try:
            with build_opener(OfficialRedirects).open(Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/pdf"}),timeout=25) as resp:
                http_date=resp.headers.get("Date")
                last_modified=resp.headers.get("Last-Modified")
                resolved_url=resp.geturl()
                raw=resp.read(12000001)
            if len(raw)<3000 or len(raw)>12000000 or not raw.startswith(b"%PDF-"):
                raise ValueError("PDF byte contract mismatch")
            import pypdf
            dest=out/(sid+".pdf");dest.write_bytes(raw)
            t="".join("".join(p.extract_text() or "" for p in pypdf.PdfReader(str(dest)).pages[:60]).split())
            symbol=code[-6:] in t
            needles=s.get("required_text",[])
            if not isinstance(needles,list) or not needles or len(needles)>5:
                raise ValueError("missing evidence text requirements")
            matches={x:x in t for x in needles}
            r.update(source_status="PDF_ORIGINAL_OBSERVED",original_bytes_verified=True,
                     sha256=hashlib.sha256(raw).hexdigest(),original_bytes=len(raw),
                     observed_at_utc=datetime.now(timezone.utc).isoformat(),
                     final_official_url=resolved_url,
                     http_response_date_unverified=http_date,
                     http_last_modified_unverified=last_modified,
                     authenticated_first_published_at=None,
                     http_headers_prove_first_publication=False,
                     issuer_text_present=symbol,required_text_presence=matches,
                     event_contents_certified=symbol and all(matches.values()))
            if r["event_contents_certified"]:
                r["source_status"]="RETROSPECTIVE_CONTENT_MATCHED"
        except (HTTPError,URLError,TimeoutError,ValueError) as ex:
            r.update(source_status="UNAVAILABLE",failure_type=type(ex).__name__,
                     status=ex.code if isinstance(ex,HTTPError) else None)
        rows.append(r)
    return {"phase":"P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE",
            "source_count":len(rows),
            "originals_observed":sum(x["original_bytes_verified"] for x in rows),
            "content_matched":sum(x["event_contents_certified"] for x in rows),
            "historical_PIT_eligible":0,"sources":rows,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--manifest",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
    q=capture(json.loads(Path(a.manifest).read_text()),root)
    (root/"quality.json").write_text(json.dumps(q,ensure_ascii=False,indent=2)+chr(10))
    print(json.dumps({k:v for k,v in q.items() if k!="sources"},ensure_ascii=False))
    for row in q["sources"]:print(json.dumps(row,ensure_ascii=False))
if __name__=="__main__":main()
