"""Replay EXACT original two-issuer historical ST CSV artifact without any market API.

Audits vendor risk labels and suspensions, not official exchange notices,
publication chronology or complete historical point-in-time coverage.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from collector.vendor_historical_st_probe import CODES, FIELDS, validate

REAL_RUN_ID = 39602222641
MAX_ZIP_BYTES = 60000
EXPECTED = {
    "sh.600421": {
        "rows": 268, "vendor_ST_1_rows": 250,
        "vendor_ST_0_rows": 18, "vendor_ST_unknown_rows": 0,
        "vendor_halted_rows": 27,
        "original_csv_sha256": "0eea6d773f99eb72898c765cfff3c47e5ad528cb32921bcc0b676ca7227fbdcb",
    },
    "sh.603019": {
        "rows": 268, "vendor_ST_1_rows": 0,
        "vendor_ST_0_rows": 268, "vendor_ST_unknown_rows": 0,
        "vendor_halted_rows": 10,
        "original_csv_sha256": "d0a79031b731f4ceb8da797bb7a5e457f90c981830b19efab88edcf1d2043992",
    },
}


def ensure(ok, why):
    if not ok:
        raise ValueError(why)


def audit(original_zip):
    p=Path(original_zip)
    ensure(p.is_file() and p.stat().st_size <= MAX_ZIP_BYTES,
           "Source archive absent or oversized")
    with ZipFile(p) as z:
        needed={"quality.json"} | {
            x.replace(".", "_")+"_vendor_ST.csv" for x in CODES
        }
        ensure(set(z.namelist()) == needed,
               "Unexpected source files or missing original ST CSV")
        ensure(all(0 < i.file_size <= 50000 for i in z.infolist()),
               "Source archive member size outside original bound")
        q=json.loads(z.read("quality.json"))
        ensure(q.get("phase")=="P3_BAOSTOCK_TWO_ISSUER_HISTORICAL_VENDOR_ST" and
               q.get("status")=="TWO_ISSUER_VENDOR_ST_OBSERVED_NOT_OFFICIAL" and
               q.get("logical_issuer_queries")==2 and
               q.get("max_source_queries")==2 and
               q.get("login_attempts")==1 and
               q.get("paid_api_calls")==0 and
               q.get("trade_gate")=="BLOCKED" and
               q.get("candidate_universe")==[] and q.get("orders")==[] and
               q.get("executable_candidates")==[] and
               q.get("source_exchange_authenticated") is False and
               q.get("historical_asof_publication_authenticated") is False and
               q.get("full_market_ST_halt_delist_complete") is False and
               q.get("vendor_isST_equivalent_to_official_notice") is False and
               q.get("data_redistribution_license_verified") is False,
               "Receipt is not research-only two-issuer historical vendor data")
        receipts=q.get("issuer_results")
        ensure(isinstance(receipts,list) and
               [r.get("code") for r in receipts]==list(CODES),
               "Two original issuer source receipts missing")
        observed=[]
        for r in receipts:
            code=r["code"]
            ensure(r.get("status")=="OBSERVED_VENDOR_ST_UNVERIFIED",
                   "Vendor source failure not eligible for replay")
            original=z.read(code.replace(".", "_")+"_vendor_ST.csv")
            reader=csv.reader(io.StringIO(original.decode("utf-8")))
            header=next(reader,[])
            ensure(tuple(header)==FIELDS,
                   "Original ST CSV schema changed")
            _,info=validate(code,list(reader))
            ensure(all(info.get(k)==v for k,v in EXPECTED[code].items()),
                   "Frozen real ST vendor statistics or digest differ")
            ensure(all(r.get(k)==info[k] for k in (
                "code","first_date","last_date","rows",
                "vendor_ST_1_rows","vendor_ST_0_rows",
                "vendor_ST_unknown_rows","vendor_halted_rows",
                "original_csv_sha256","original_csv_bytes",
            )), "Original source receipt differs from actual source bytes")
            observed.append(info)
    ensure(sum(x["rows"] for x in observed)==536, "Original vendor row total changed")
    return {
        "phase": "P3_TWO_ISSUER_REAL_VENDOR_ST_SOURCE_REPLAY",
        "status": "ORIGINAL_CSV_SHA_VERIFIED_VENDOR_ST_ONLY",
        "capture_run_id": REAL_RUN_ID,
        "issuer_count": len(observed),
        "total_source_rows": 536,
        "vendor_ST_1_rows": sum(x["vendor_ST_1_rows"] for x in observed),
        "vendor_ST_0_rows": sum(x["vendor_ST_0_rows"] for x in observed),
        "vendor_ST_unknown_rows": sum(x["vendor_ST_unknown_rows"] for x in observed),
        "vendor_halted_rows": sum(x["vendor_halted_rows"] for x in observed),
        "original_csv_replayed_in_this_run": True,
        "exchange_ST_status_verified": False,
        "historical_publication_instant_verified": False,
        "complete_mainboard_universe_verified": False,
        "all_original_CSV_archived_permanently": False,
        "risk_labels_research_only": True,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "paid_api_calls": 0, "issuer_receipts": observed,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifact", required=True)
    p.add_argument("--out", required=True)
    args=p.parse_args()
    r=audit(args.artifact)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r,ensure_ascii=False))

if __name__=="__main__":
    main()
