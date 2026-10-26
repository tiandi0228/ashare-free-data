"""Bounded original-PDF capture for actual P1 issuer CNINFO index candidates.
A live download is not historical first-publication or PIT state certification.
"""
import argparse,hashlib,json,re
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen

URL_RE=re.compile(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/(\d+)\.PDF",re.I)
ISSUER_RE=re.compile(r"(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))\d{3}")

# Ranking is only a download priority, NOT a certified event classification.
# CNINFO titles are index metadata; the actual PDF must still be replayed.
RISK_WORDS=("停牌","复牌","风险警示","退市","终止上市","暂停上市","上市公告书")
def _research_priority(title):
    if not isinstance(title,str) or len(title)>200:
        raise ValueError("invalid unverified index title")
    upper=title.upper()
    return (2 if any(term in title for term in RISK_WORDS) else
            1 if re.search(r"(?<![A-Z])\*?ST(?![A-Z])",upper) else 0)

def choose(report,limit=3,scout=None):
    if report.get("phase")!="P3_REAL_P1_LIVE_INDEX_DISCOVERY" or report.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid P1 target index report")
    days_by_issuer={}
    if scout is not None:
        if (scout.get("phase")!="P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE"
            or scout.get("trade_gate")!="BLOCKED"
            or scout.get("official_PIT_verified") is not False):
            raise ValueError("unsafe historical decision-day source")
        for target in scout["targets"]:
            issuer=target["issuer"]
            days=target["observed_decision_dates"]
            if (not ISSUER_RE.fullmatch(issuer) or issuer in days_by_issuer
                or not isinstance(days,list) or not days or days!=sorted(set(days))):
                raise ValueError("invalid frozen source dates")
            try:dates=[date.fromisoformat(x) for x in days]
            except (ValueError,TypeError) as exc:raise ValueError("bad historical source date") from exc
            priority=target.get("vendor_halt_transition_research_days") or target.get("vendor_suspended_research_days") or days
            if not isinstance(priority,list) or not priority or any(d not in days for d in priority):
                raise ValueError("vendor halt date not in P1 checked decision-day scope")
            days_by_issuer[issuer]=[date.fromisoformat(d) for d in priority]
        if [item["issuer"] for item in report["results"]]!=list(days_by_issuer):
            raise ValueError("official index source and decision pool mismatch")
    selected=[];seen=set()
    for item in report["results"]:
        issuer=item["issuer"]
        if not ISSUER_RE.fullmatch(issuer) or issuer in seen:
            raise ValueError("invalid or duplicate issuer")
        seen.add(issuer)
        candidates=[]
        for candidate in item["candidates"]:
            url=candidate.get("official_pdf_url")
            match=URL_RE.fullmatch(url or "")
            if (not match or candidate.get("announcement_id")!=match.group(1)
                or candidate.get("historical_PIT_verified") is not False):
                raise ValueError("invalid official index candidate")
            title=candidate.get("announcement_title_unverified","")
            score=_research_priority(title)
            # URL directory dates are only research hints, NOT an independently
            # authenticated first-publication timestamp or historical effective day.
            url_day=date.fromisoformat(url.split("/finalpage/",1)[1][:10])
            days=days_by_issuer.get(issuer)
            possible=days is not None and any(url_day<=day for day in days)
            nearest=min((abs((day-url_day).days) for day in days),default=99999) if days else 99999
            title_reason="RISK_TITLE_RESEARCH_PRIORITY" if score else "INDEX_ORDER_FALLBACK"
            if days:
                title_reason=("POSSIBLY_PRE_DECISION_RESEARCH_PRIORITY" if possible else
                              "POST_DECISION_URL_DAY_UNUSABLE_ASOF_RESEARCH")
            selected_record={"issuer":issuer,"announcement_id":match.group(1),
                 "url":url,"announcement_title_unverified":title,
                 "index_page_observed":candidate.get("index_page_observed"),
                 "original_pdf_url_date_unverified":url_day.isoformat(),
                 "could_precede_target_decision_day_unverified":possible,
                 "selection_reason":title_reason,
                 "first_publication_time_authenticated":False}
            candidates.append(((int(possible) if days else 1,score,-nearest),selected_record))
        if candidates:
            # A pre-decision URL date is useful for discovery, not causality proof.
            _,choice=max(candidates,key=lambda entry:entry[0])
            selected.append(choice)
        if len(selected)>=limit:break
    return selected

def capture(report,out,fetch=None,scout=None):
    selected=choose(report,scout=scout)
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
    p.add_argument("--scout")
    args=p.parse_args()
    scout=json.loads(Path(args.scout).read_text()) if args.scout else None
    r=capture(json.loads(Path(args.index).read_text()),args.out,scout=scout)
    (Path(args.out)/"quality.json").write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="sources"}))
if __name__=="__main__":main()
