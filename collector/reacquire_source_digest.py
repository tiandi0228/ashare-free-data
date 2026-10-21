"""One bounded source-reacquisition stability test, NEVER an archival guarantee.

Two known source issuer codes. Query exactly the original capture range and
fields; compare byte-level SHA with previous independently audited originals.
Only SHA & counts emitted; original vendor rows never redistributed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from collector.baostock_batch import FIELDS, START, END
from collector.audit_delisted_archive import verify_rows

CODES=("sh.600421", "sh.600000")
FIRST_RUN=39589103403
PRIOR_RUNS=(39572697952,39573265839)


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def originals(old, new):
    legacy=old.get("audit_report",{})
    fresh=new.get("replay_report",{})
    require(old.get("capture_run_ids")==list(PRIOR_RUNS) and
            legacy.get("issuer_count")==16 and
            legacy.get("original_source_rows")==7760 and
            legacy.get("trade_gate")=="BLOCKED" and
            legacy.get("historical_point_in_time_universe_verified") is False,
            "Previous sixteen-source audit not eligible")
    require(new.get("source_run_id")==FIRST_RUN and
            new.get("actual_replay_verified") is True and
            fresh.get("original_csv_issuer_count")==8 and
            fresh.get("original_csv_total_rows")==3803 and
            fresh.get("trade_gate")=="BLOCKED",
            "Previously replayed delisted originals not eligible")
    matches={
        "sh.600421": next((x for x in fresh.get("source_receipts", [])
                         if x.get("code")=="sh.600421"),None),
        "sh.600000": next((x for x in legacy.get("issuers",[])
                         if x.get("code")=="sh.600000"),None),
    }
    require(all(matches.values()), "Unknown original source identity")
    return {
        "sh.600421": (matches["sh.600421"]["original_csv_sha256"],
                      matches["sh.600421"]["source_rows"]),
        "sh.600000": (matches["sh.600000"]["source_sha256"],
                      matches["sh.600000"]["source_rows"]),
    }


def reacquire(provider, old, new):
    expected=originals(old,new)
    report={
        "phase":"P1_ZERO_COST_BOUNDED_HISTORICAL_SOURCE_REACQUISITION",
        "status":"BLOCKED_PARTIAL",
        "source_codes":list(CODES),
        "query_range":[START,END],
        "query_fields":list(FIELDS),
        "source_record_baseline_not_official_pit":True,
        "login_attempts":1,"issuer_queries":0,"max_issuer_queries":2,
        "source_reports":[],
        "source_raw_csv_republished":False,
        "source_raw_bytes_durably_archived":False,
        "provider_historical_version_can_change":True,
        "publication_instant_authenticated":False,
        "official_exchange_historical_risk_verified":False,
        "all_market_replay_ready":False,
        "paid_api_calls":0,"trade_gate":"BLOCKED",
        "orders":[],"candidate_universe":[],"executable_candidates":[],
    }
    logged=False
    try:
        login=provider.login()
        require(login.error_code=="0","Provider login rejected")
        logged=True
        for code in CODES:
            entry={"code":code,"status":"ERROR"}
            report["issuer_queries"]+=1
            try:
                reply=provider.query_history_k_data_plus(
                    code,fields=",".join(FIELDS),
                    start_date=START,end_date=END,frequency="d",adjustflag="3"
                )
                require(reply.error_code=="0" and list(reply.fields)==FIELDS,
                        "Provider response schema changed")
                rows=[]
                while reply.next():
                    rows.append(reply.get_row_data())
                    require(len(rows)<=600,"Source page limit exceeded")
                require(all(len(row)==len(FIELDS) and
                            all(isinstance(v,str) for v in row)
                            for row in rows),"Malformed source row")
                raw=(",".join(FIELDS)+"\n"+
                     "".join(",".join(row)+"\n" for row in rows)).encode("utf-8")
                details=verify_rows(code,raw)
                baseline_sha, baseline_rows=expected[code]
                equal=(details["original_csv_sha256"]==baseline_sha and
                       details["source_rows"]==baseline_rows)
                entry.update({
                    "status":"BYTE_IDENTICAL_NOW_NOT_PERMANENT" if equal
                              else "SOURCE_HISTORY_VERSION_DRIFT",
                    "previous_SHA256":baseline_sha,
                    "observed_SHA256":details["original_csv_sha256"],
                    "previous_source_rows":baseline_rows,
                    "observed_source_rows":details["source_rows"],
                    "same_SHA256_and_row_count":equal,
                    "original_source_bytes_redistributed":False,
                })
            except Exception as exc:
                entry["error_type"]=type(exc).__name__
            report["source_reports"].append(entry)
    except Exception as exc:
        report["login_failure_type"]=type(exc).__name__
    finally:
        if logged:
            try: provider.logout()
            except Exception: report["logout_error"]=True
    if (len(report["source_reports"])==2 and
            all(e.get("same_SHA256_and_row_count") is True
                for e in report["source_reports"])):
        report["status"]="TWO_SOURCES_REACQUIRED_IDENTICAL_NOW_NO_DURABLE_STORAGE"
    elif any(e.get("status")=="SOURCE_HISTORY_VERSION_DRIFT"
             for e in report["source_reports"]):
        report["status"]="BLOCKED_VENDOR_HISTORICAL_REVISION_DETECTED"
    report["observed_at_utc"]=datetime.now(timezone.utc).isoformat()
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--old",default="reports/p1_pilot_16_source_digests_20261021.json")
    p.add_argument("--new",default="reports/p1_delisted_8_source_digests_20261021.json")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    import baostock as bs
    old=json.loads(Path(args.old).read_text(encoding="utf-8"))
    new=json.loads(Path(args.new).read_text(encoding="utf-8"))
    q=reacquire(bs,old,new)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(q,ensure_ascii=False))
    raise SystemExit(0 if q["status"]=="TWO_SOURCES_REACQUIRED_IDENTICAL_NOW_NO_DURABLE_STORAGE" else 2)

if __name__=="__main__":
    main()
