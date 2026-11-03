"""Structural point-in-time availability audit for research inputs, NO TRADES.

Never accepts an observation whose publish/available/effective timestamp
comes from after its decision instant. A passing schema audit is NOT historical
PIT authentication; independent original vendor disclosure evidence remains
required. All timestamps must carry UTC offsets.
"""
import argparse,datetime as dt,json,re
from pathlib import Path

CODE=re.compile(r"(?:00\d{4}|30\d{4}|60\d{4}|68\d{4}|8\d{5})\Z")
HEX=re.compile(r"[0-9a-f]{64}\Z")
def parse_stamp(value):
    if not isinstance(value,str):raise ValueError("timestamp absent")
    try:t=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as e:raise ValueError("invalid timestamp") from e
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError("timezone offset required")
    return t.astimezone(dt.timezone.utc)

def audit(data):
    base={"phase":"P1_HISTORICAL_PIT_STRUCTURAL_PREFLIGHT",
          "historical_PIT_verified":False,"full_market_bars_certified":False,
          "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
          "buy_recommendations_authorized":False}
    if not isinstance(data,dict) or not isinstance(data.get("observations"),list):
        return dict(base,status="REJECTED",issues=["MISSING_POINT_IN_TIME_EVIDENCE"])
    try:decision=parse_stamp(data["decision_at"])
    except (ValueError,KeyError):
        return dict(base,status="REJECTED",issues=["INVALID_DECISION_TIMESTAMP"])
    rows=data["observations"]
    if not rows or len(rows)>1000:
        return dict(base,status="REJECTED",issues=["MISSING_OR_OVERSIZED_OBSERVATIONS"])
    issues=[];seen=set()
    for i,row in enumerate(rows):
        if not isinstance(row,dict):
            issues.append(f"ROW_{i}_MALFORMED");continue
        code=row.get("code")
        if not isinstance(code,str) or not CODE.fullmatch(code):
            issues.append(f"ROW_{i}_INVALID_CODE");continue
        key=(code,row.get("field"))
        if not isinstance(row.get("field"),str) or not re.fullmatch(r"[a-z_]{2,40}",row["field"]) or key in seen:
            issues.append(f"ROW_{i}_FIELD_OR_DUPLICATE_INVALID");continue
        seen.add(key)
        try:
            observed=parse_stamp(row["observed_at"])
            published=parse_stamp(row["published_at"])
            available=parse_stamp(row["available_at"])
            effective=parse_stamp(row["effective_from"])
            ends=parse_stamp(row["effective_to"]) if row.get("effective_to") is not None else None
        except (KeyError,ValueError):
            issues.append(f"ROW_{i}_TIMESTAMP_UNVERIFIABLE");continue
        if not (observed<=published<=available<=decision):
            issues.append(f"ROW_{i}_FUTURE_OR_INCONSISTENT_PUBLICATION")
        if effective>decision or (ends is not None and (ends<=effective or decision>=ends)):
            issues.append(f"ROW_{i}_NOT_EFFECTIVE_AT_DECISION")
        if not isinstance(row.get("original_source_sha256"),str) or not HEX.fullmatch(row["original_source_sha256"]):
            issues.append(f"ROW_{i}_ORIGINAL_EVIDENCE_HASH_MISSING")
        if row.get("source_archived") is not True:
            issues.append(f"ROW_{i}_SOURCE_ARCHIVE_NOT_CONFIRMED")
    return dict(base,status=("STRUCTURAL_CHECK_PASSED_PIT_UNVERIFIED" if not issues else "REJECTED"),
                checked_observations=len(rows),issues=issues,
                outstanding=["INDEPENDENT_VENDOR_PUBLICATION_TIMESTAMPS_UNVERIFIED",
                             "HISTORICAL_ST_DELISTING_CORPORATE_ACTION_UNIVERSE_NOT_CERTIFIED",
                             "AS_OF_SNAPSHOT_REPLAY_NOT_CERTIFIED"])

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    try:r=audit(json.loads(Path(a.input).read_text()))
    except (OSError,ValueError,UnicodeError):r=audit(None)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":r["status"],"trade_gate":"BLOCKED"}))
if __name__=="__main__":main()
