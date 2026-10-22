"""Inspect original official PDF date contexts, without granting event effectiveness.

Requires the archived bytes AND hash-linked original receipt. Date snippets are
research cues only; they cannot certify issuer state or availability at time.
"""
import argparse,hashlib,json,re
from pathlib import Path
from pypdf import PdfReader

def inspect(root, manifest):
    root=Path(root)
    receipts=list(root.rglob("quality.json"))
    if len(receipts)!=1: raise ValueError("expected exactly one original receipt")
    q=json.loads(receipts[0].read_text())
    if q.get("phase")!="P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE" or q.get("trade_gate")!="BLOCKED":
        raise ValueError("unexpected receipts")
    wanted={s["id"]:s for s in manifest}
    if len(wanted)!=len(manifest) or len(wanted)!=6: raise ValueError("wrong manifest scope")
    src=q["sources"]
    if len(src)!=6:raise ValueError("missing sources")
    results=[]
    for r in src:
        sid=r["source_id"];s=wanted.pop(sid)
        path=receipts[0].parent/(sid+".pdf")
        raw=path.read_bytes()
        if (hashlib.sha256(raw).hexdigest()!=r.get("sha256") or
            r.get("event_contents_certified") is not True or
            r.get("issuer")!=s["issuer"] or r.get("event_kind")!=s["kind"]):
            raise ValueError("original PDF digest or event identity mismatch")
        reader=PdfReader(str(path));text="".join("".join(p.extract_text() or "" for p in reader.pages[:60]).split())
        matched=[]
        for needle in s["required_text"]:
            if not re.fullmatch(r"20[0-9]{2}年[0-9]{1,2}月[0-9]{1,2}日",needle):continue
            locations=[m.start() for m in re.finditer(re.escape(needle),text)]
            if not locations: raise ValueError("previously verified date vanished")
            matched.append({"date_text":needle,"occurrences":len(locations),
                "nearby_text_samples":[text[max(0,i-80):i+len(needle)+80] for i in locations[:3]],
                "effective_date_certified":False,"historical_PIT_verified":False})
        results.append({"issuer":s["issuer"],"source_id":sid,"event_family":s["kind"],
                        "original_sha256":r["sha256"],"date_contexts":matched,
                        "issuer_state_transition_authenticated":False})
    if wanted:raise ValueError("unmatched manifest sources")
    return {"phase":"P3_SIX_ORIGINAL_PDF_DATE_CONTEXT_INSPECTION",
            "verified_originals":len(results),
            "dates_with_context":sum(len(x["date_contexts"]) for x in results),
            "effective_date_certified_count":0,"PIT_eligible_events":0,
            "results":results,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--manifest",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    out=inspect(a.root,json.loads(Path(a.manifest).read_text()))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="results"},ensure_ascii=False))
if __name__=="__main__":main()
