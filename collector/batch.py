"""Free bounded research-only batch capture, resumable across *different* Actions runs.

Input codes are a reviewed manifest, not a verified point-in-time exchange pool.
At most two SDK attempts per code for connection/timeouts only. No signals or trades.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from collector.probe import check_frame, START, END

MAX_BATCH = 8
CODE = re.compile(r"(?:00[0-3]|60[0-5])[0-9]{3}\Z")

def load_manifest(path):
    raw = Path(path).read_bytes()
    if len(raw) > 100_000:
        raise ValueError("Manifest too large")
    codes = [x.strip() for x in raw.decode("utf-8-sig").splitlines() if x.strip() and not x.lstrip().startswith("#")]
    if not codes or len(codes) > 200 or len(set(codes)) != len(codes):
        raise ValueError("Manifest must contain 1-200 unique codes")
    if any(not CODE.fullmatch(x) for x in codes):
        raise ValueError("Only 6-digit Shanghai/Shenzhen mainboard formats allowed")
    return codes, hashlib.sha256(raw).hexdigest()

def capture(manifest, batch_index, dest, provider=None):
    codes, manifest_sha = load_manifest(manifest)
    batches = (len(codes)+MAX_BATCH-1)//MAX_BATCH
    if batch_index < 0 or batch_index >= batches:
        raise ValueError("Batch index outside manifest")
    selected = codes[batch_index*MAX_BATCH:(batch_index+1)*MAX_BATCH]
    if provider is None:
        import akshare as provider
    out = Path(dest); out.mkdir(parents=True, exist_ok=True)
    results = []
    logical_calls = 0
    for code in selected:
        row = {"code":code,"status":"ERROR","publisher_authenticated":False}
        for attempt in range(1,3):
            logical_calls += 1
            row["attempts"] = attempt
            try:
                frame = provider.stock_zh_a_hist(
                    symbol=code,period="daily",start_date=START.strftime("%Y%m%d"),
                    end_date=END.strftime("%Y%m%d"),adjust="",timeout=12)
                raw, dates = check_frame(frame,code)
                (out / (code+".csv")).write_bytes(raw)
                row.update(status="OBSERVED_UNVERIFIED",rows=len(dates),first=dates[0].isoformat(),
                           last=dates[-1].isoformat(),sha256=hashlib.sha256(raw).hexdigest())
                break
            except (ConnectionError, TimeoutError) as exc:
                row["error_type"] = type(exc).__name__
                if attempt == 2:
                    break
            except Exception as exc:
                row["error_type"] = type(exc).__name__
                break
        results.append(row)
    succeeded=sum(x["status"]=="OBSERVED_UNVERIFIED" for x in results)
    report={"phase":"PUBLIC_FREE_BOUND_BATCH","status":"OBSERVED_UNVERIFIED" if all(x["status"]=="OBSERVED_UNVERIFIED" for x in results) else "BLOCKED_PARTIAL",
            "observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "successful_issuer_count":succeeded,
            "failed_issuer_count":len(selected)-succeeded,
            "observed_issuer_coverage_fraction":succeeded/len(selected),
            "manifest_sha256":manifest_sha,"batch_index":batch_index,"batch_count":batches,
            "batch_cap":MAX_BATCH,"requested_count":len(selected),"logical_sdk_calls":logical_calls,"max_attempts_per_issuer":2,
            "underlying_http_count_verified":False,"paid_api_calls":0,"source":"Eastmoney via AkShare",
            "issuers":results,"official_exchange_publisher_verified":False,
            "historical_point_in_time_universe_verified":False,"historical_ST_halt_delist_verified":False,
            "full_market_backfill_performed":False,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    (out/"quality.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report["status"]=="OBSERVED_UNVERIFIED" else 2

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",default="manifests/pilot_issuers.txt")
    p.add_argument("--batch-index",type=int,required=True)
    p.add_argument("--out",required=True)
    x=p.parse_args()
    raise SystemExit(capture(x.manifest,x.batch_index,x.out))

if __name__=="__main__":
    main()
