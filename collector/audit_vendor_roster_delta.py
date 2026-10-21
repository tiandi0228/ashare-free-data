"""Quantify change between TWO independently SHA-verified vendor dated rosters.

Two retrospectively queried vendor lists may establish *observed set drift*,
but not point-in-time exchange membership, IPO, official delisting, or negative
risk coverage. Never output a tradable stock universe or trading instructions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from collector.audit_dated_rosters import audit_archive
from collector.baostock_dated_universe import DATES, FIELDS, MAINBOARD

MIN_INTERSECTION = 2000


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def compare_rosters(early, late, minimum_intersection=MIN_INTERSECTION):
    """Inputs are code,tradeStatus,code_name rows; never publish row content."""
    parsed=[]
    for rows in (early,late):
        require(isinstance(rows,list) and len(rows)>=1,
                "Empty or wrong vendor membership dataset")
        by_code={}
        for row in rows:
            require(isinstance(row,(tuple,list)) and len(row)==len(FIELDS),
                    "Malformed vendor roster row")
            code,status,name=row
            require(isinstance(code,str) and MAINBOARD.fullmatch(code) and
                    status in ("0","1") and
                    isinstance(name,str) and name.strip(),
                    "Unknown provisional board member or vendor status")
            require(code not in by_code, "Duplicated code in a dated roster")
            by_code[code]=status
        parsed.append(by_code)
    a,b=parsed
    common=set(a)&set(b)
    removed=set(a)-set(b)
    added=set(b)-set(a)
    require(len(common)>=minimum_intersection,
            "Insufficient verified two-date cohort overlap")
    require(len(common)+len(removed)==len(a) and
            len(common)+len(added)==len(b),
            "Vendor historical membership accounting failed")
    changes={
        f"{before}_to_{after}":sum(a[code]==before and b[code]==after
                              for code in common)
        for before in ("0","1")
        for after in ("0","1")
    }
    require(sum(changes.values())==len(common),
            "Observed status transitions not accounted for")
    def digest(codes):
        return hashlib.sha256(
            ("\n".join(sorted(codes))+"\n").encode("utf-8")
        ).hexdigest()
    return {
        "early_issuer_count":len(a),
        "late_issuer_count":len(b),
        "common_issuer_count":len(common),
        "early_only_count":len(removed),
        "late_only_count":len(added),
        "combined_unique_issuer_codes":len(common|removed|added),
        "common_code_set_sha256":digest(common),
        "early_only_code_set_sha256":digest(removed),
        "late_only_code_set_sha256":digest(added),
        "vendor_status_changes_in_common_codes":changes,
        "sh_600421_present_in_early_snapshot":"sh.600421" in a,
        "sh_600421_present_in_late_snapshot":"sh.600421" in b,
        "membership_delta_proves_IPO_or_delisting":False,
        "retrospective_vendor_membership_is_PIT":False,
        "validated_exchange_event_effective_dates":False,
    }


def audit_delta(zip_path):
    base=audit_archive(zip_path)  # independently checks ALL frozen original SHAs
    require(base["status"]=="ORIGINAL_TWO_VENDOR_ROSTERS_REPLAYED_PIT_BLOCKED" and
            base["issuer_pool_size_2025_05_26"]==3181 and
            base["issuer_pool_size_2026_10_20"]==3195 and
            base["trade_gate"]=="BLOCKED" and
            base["dated_originals_replayed_in_this_run"] is True,
            "Original two dates have not been independently authenticated")
    with ZipFile(zip_path) as z:
        rosters=[]
        for day in DATES:
            raw=z.read(f"mainboard_prefix_{day}.csv")
            csvreader=csv.reader(io.StringIO(raw.decode("utf-8")))
            require(tuple(next(csvreader,()))==FIELDS,
                    "Original subset schema no longer matches audit")
            rosters.append(list(csvreader))
    changes=compare_rosters(*rosters)
    require((changes["early_issuer_count"],changes["late_issuer_count"]) ==
            (3181,3195), "Vendor member numbers contradict source audit")
    return {
        "phase":"P1_TWO_VENDOR_DATED_ROSTERS_MEMBERSHIP_DELTA",
        "status":"RESEARCH_VENDOR_COHORT_DELTA_REPLAYED_OFFICIAL_PIT_BLOCKED",
        "original_roster_source_run":39613467121,
        "original_sha_replay_confirmed_again_in_this_run":True,
        "vendor_date_early":DATES[0],
        "vendor_date_late":DATES[1],
        "source_publication_time_at_historical_dates_verified":False,
        "exchange_authoritative_issuer_membership_verified":False,
        "historical_official_ST_halt_delist_verified":False,
        "original_source_bytes_permanently_archived":False,
        "two_year_history_of_all_candidates_verified":False,
        "trade_gate":"BLOCKED",
        "candidate_universe":[],"orders":[],"executable_candidates":[],
        "paid_api_calls":0,
        "vendor_membership_delta":changes,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifact",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    out=audit_delta(args.artifact)
    dest=Path(args.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",
                    encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False))


if __name__=="__main__":
    main()
