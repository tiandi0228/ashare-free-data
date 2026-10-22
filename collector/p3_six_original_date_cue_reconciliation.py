"""Conservative date-cue reconciliation for original PDF receipts.

Dates extracted from verified PDFs are contextual cues, not certified event
effective dates or historical publication availability.
"""
import argparse,json,re
from collections import Counter
from pathlib import Path

def build(receipt,manifest):
    if receipt.get("phase")!="P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE" or receipt.get("trade_gate")!="BLOCKED":
        raise ValueError("invalid original receipts")
    src=receipt.get("sources")
    if not isinstance(src,list) or len(src)!=6:
        raise ValueError("expected six real source records")
    specs={s["id"]:s for s in manifest}
    if len(specs)!=6 or len(manifest)!=6:
        raise ValueError("duplicate or missing manifest IDs")
    output=[]
    for r in src:
        s=specs.pop(r["source_id"])
        if r.get("issuer")!=s["issuer"] or r.get("event_kind")!=s["kind"] or r.get("url")!=s["url"]:
            raise ValueError("provenance mismatches original request")
        needles=s["required_text"]
        if not needles or not isinstance(needles,list):
            raise ValueError("missing original text probes")
        checks=r.get("required_text_presence",{})
        complete=(r.get("original_bytes_verified") is True and
                  r.get("event_contents_certified") is True and
                  r.get("issuer_text_present") is True and
                  r.get("PIT_publication_verified") is False and
                  all(checks.get(t) is True for t in needles))
        cues=[t for t in needles if re.fullmatch(r"20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日",t)]
        output.append({"issuer":s["issuer"],"source_id":s["id"],
                       "event_family":s["kind"],"date_text_cues":cues if complete else [],
                       "original_pdf_text_checks_passed":complete,
                       "effective_date_semantics_certified":False,
                       "event_transition_certified":False,
                       "historically_available_at_date":False,
                       "historical_PIT_eligible":False})
    if specs:
        raise ValueError("source receipts incomplete")
    return {"phase":"P3_SIX_ORIGINAL_DATE_CUE_RECONCILIATION",
            "source_count":len(output),
            "sources_with_validated_date_text_cues":sum(bool(x["date_text_cues"]) for x in output),
            "individual_date_text_cues":sum(len(x["date_text_cues"]) for x in output),
            "confirmed_historical_effective_date_events":0,
            "PIT_eligible_event_count":0,
            "events":output,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--receipt",required=True);p.add_argument("--manifest",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=build(json.loads(Path(a.receipt).read_text()),json.loads(Path(a.manifest).read_text()))
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="events"},ensure_ascii=False))
if __name__=="__main__":main()
