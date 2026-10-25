"""Reject historical publication-time claims inferred only from PDF retrieval metadata."""
import argparse,json
from pathlib import Path

def audit(receipt):
    if receipt.get("phase")!="P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE" or receipt.get("trade_gate")!="BLOCKED":
        raise ValueError("unexpected or unsafe receipt")
    sources=receipt.get("sources")
    if not isinstance(sources,list) or not sources:raise ValueError("missing sources")
    for row in sources:
        if (row.get("PIT_publication_verified") is not False or
            row.get("authenticated_first_published_at") is not None or
            row.get("http_headers_prove_first_publication") is not False):
            raise ValueError("unsupported historical publication claim")
        if row.get("original_bytes_verified") is True:
            if not row.get("observed_at_utc") or not row.get("sha256"):
                raise ValueError("retrieved original lacks observation time or digest")
    return {"phase":"P3_PUBLICATION_TIME_PROVENANCE_GATE",
            "retrieval_observations":sum(x.get("original_bytes_verified") is True for x in sources),
            "historical_first_publication_authenticated":0,
            "historical_PIT_eligible":0,"http_metadata_is_historical_publication_proof":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=audit(json.loads(Path(a.receipt).read_text()))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":main()
