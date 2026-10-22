"""Independent eight-issuer vendor recapture comparison (metadata only).

Input files are capture *quality* JSON receipts, not wrapper reports. The
comparison cannot certify exchange PIT membership or authorize trades.
"""
import argparse
import json
from pathlib import Path

def compare(first, second):
    def validate(q):
        if q.get("phase") != "P1_BOUNDED_VENDOR_EARLY_ONLY_HINDSIGHT_RESEARCH_HISTORY":
            raise ValueError("wrong phase")
        rows = q.get("results")
        if not isinstance(rows, list) or len(rows) != 8:
            raise ValueError("expected eight original issuer receipts")
        codes = q.get("issuer_codes")
        if not isinstance(codes, list) or len(codes) != 8 or len(set(codes)) != 8:
            raise ValueError("invalid cohort")
        if [r.get("code") for r in rows] != codes:
            raise ValueError("result order or identity mismatch")
        if q.get("source_observed_issuers") != 8 or q.get("logical_source_queries") != 8:
            raise ValueError("incomplete capture")
        if q.get("trade_gate") != "BLOCKED" or q.get("orders") != []:
            raise ValueError("unsafe trade state")
        if q.get("official_historical_PIT_universe_verified") is not False:
            raise ValueError("unverified official history")
        for r in rows:
            sha = r.get("original_source_sha256")
            if r.get("status") != "VENDOR_HISTORY_OBSERVED_NOT_PIT" or not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("invalid original source sha")
            if r.get("original_source_rows", 0) <= 0 or r["original_source_rows"] != r.get("vendor_trade_status_1_rows", -1) + r.get("vendor_trade_status_0_rows", -1):
                raise ValueError("invalid row conservation")
        if sum(r["original_source_rows"] for r in rows) != q.get("source_observed_rows"):
            raise ValueError("invalid cohort row conservation")
        return {r["code"]: r for r in rows}
    a,b=validate(first),validate(second)
    if first.get("capture_run_id") is None or second.get("capture_run_id") is None or first["capture_run_id"] == second["capture_run_id"]:
        raise ValueError("independent distinct capture run ids required")
    if set(a) != set(b):
        raise ValueError("cannot compare different cohorts")
    mismatches = [c for c in sorted(a) if a[c]["original_source_sha256"] != b[c]["original_source_sha256"] or a[c]["original_source_rows"] != b[c]["original_source_rows"]]
    return {"status":"INDEPENDENT_VENDOR_RECAPTURE_MATCH_PIT_BLOCKED" if not mismatches else "VENDOR_RECAPTURE_CHANGED_PIT_BLOCKED",
            "first_capture_run_id":first["capture_run_id"],"second_capture_run_id":second["capture_run_id"],
            "issuer_count":8,"matching_issuers":8-len(mismatches),"mismatching_codes":mismatches,
            "official_historical_PIT_universe_verified":False,"source_replay_durable":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"paid_api_calls":0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--first",required=True);p.add_argument("--second",required=True);p.add_argument("--out",required=True)
    args=p.parse_args()
    a=json.loads(Path(args.first).read_text(encoding="utf-8"))
    b=json.loads(Path(args.second).read_text(encoding="utf-8"))
    report=compare(a,b)
    dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))
    raise SystemExit(0 if report["matching_issuers"]==8 else 2)

if __name__=="__main__":
    main()
