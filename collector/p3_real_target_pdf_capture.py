"""Bounded original-PDF capture for actual P1 issuer CNINFO index candidates.
A live download is not historical first-publication or PIT state certification.
"""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen

URL_RE=re.compile(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/(\d+)\.PDF",re.I)
ISSUER_RE=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}")

def choose(report,limit=3):
    if report.get("phase")!="P3_REAL_P1_LIVE_INDEX_DISCOVERY" or report.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid P1 target index report")
    selected=[]
    for item in report["results"]:
        issuer=item["issuer"]
        if not ISSUER_RE.fullmatch(issuer):raise ValueError("invalid issuer")
        for candidate in item["candidates"]:
            url=candidate.get("official_pdf_url")
            match=URL_RE.fullmatch(url or "")
            if (not match or candidate.get("announcement_id")!=match.group(1)
                or candidate.get("historical_PIT_verified") is not False):
                raise ValueError("invalid official index candidate")
            selected.append({"issuer":issuer,"announcement_id":match.group(1),"url":url})
            break
        if len(selected)>=limit:break
    return selected

def capture(report,out,fetch=None):
    selected=choose(report)
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    results=[]
    for entry in selected:
        result={**entry,"status":"UNAVAILABLE_NOT_NO_RISK","original_bytes_verified":False,
                "historical_first_publication_authenticated":False,"historical_PIT_verified":False}
        try:
            if fetch is None:
                request=Request(entry["url"],headers={"User-Agent":"Mozilla/5.0","Accept":"application/pdf"})
                with urlopen(request,timeout=18) as response:
                    if response.geturl()!=entry["url"]:raise ValueError("unexpected redirect")
                    raw=response.read(4000001)
            else:raw=fetch(entry["url"])
            if not isinstance(raw,bytes) or not 3000<=len(raw)<=4000000 or not raw.startswith(b"%PDF-"):
                raise ValueError("invalid original PDF bytes")
            name=entry["issuer"].replace(".","_")+"_"+entry["announcement_id"]+".pdf"
            (root/name).write_bytes(raw)
            result.update(status="PDF_ORIGINAL_RETRIEVED_RESEARCH_ONLY",
                          original_bytes_verified=True,original_file=name,
                          sha256=hashlib.sha256(raw).hexdigest(),
                          observed_at_utc=datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            result["error_type"]=type(exc).__name__
        results.append(result)
    return {"phase":"P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE","attempted":len(selected),
            "retrieved":sum(x["original_bytes_verified"] for x in results),
            "sources":results,"historical_first_publication_authenticated":False,
            "historical_PIT_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for n in ("index","out"):p.add_argument("--"+n,required=True)
    args=p.parse_args()
    r=capture(json.loads(Path(args.index).read_text()),args.out)
    (Path(args.out)/"quality.json").write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="sources"}))
if __name__=="__main__":main()
