"""Reject historical publication-time claims inferred only from PDF retrieval metadata."""
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path

DIGEST=re.compile(r"[0-9a-f]{64}\Z")

def _observation_instant(value):
    if not isinstance(value,str):raise ValueError("missing observation timestamp")
    try: observed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise ValueError("invalid observation timestamp") from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("observation timestamp missing timezone")
    return observed.astimezone(timezone.utc)

def audit(receipt):
    if (not isinstance(receipt,dict) or receipt.get("phase")!="P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE" or receipt.get("trade_gate")!="BLOCKED"):
        raise ValueError("unexpected or unsafe receipt")
    sources=receipt.get("sources")
    if not isinstance(sources,list) or not 1<=len(sources)<=10000:raise ValueError("missing or unbounded sources")
    observations=0
    for row in sources:
        if not isinstance(row,dict):raise ValueError("invalid source row")
        if (row.get("PIT_publication_verified") is not False or
            row.get("authenticated_first_published_at") is not None or
            row.get("http_headers_prove_first_publication") is not False):
            raise ValueError("unsupported historical publication claim")
        verified=row.get("original_bytes_verified")
        if type(verified) is not bool:raise ValueError("invalid verification flag")
        if verified:
            _observation_instant(row.get("observed_at_utc"))
            digest=row.get("sha256")
            if not isinstance(digest,str) or not DIGEST.fullmatch(digest):
                raise ValueError("invalid verified original SHA-256")
            observations+=1
    return {"phase":"P3_PUBLICATION_TIME_PROVENANCE_GATE",
            "retrieval_observations":observations,
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
