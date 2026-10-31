"""Bounded *current* Baostock MA20 research pilot on audited frozen P1 originals.

P1 remains frozen at 2026-10-20. This separate, at-most-eight-issuer
observation never mutates the baseline, authenticates PIT, or opens orders.
"""
import argparse,csv,hashlib,json,re
from collections import deque
from datetime import date,datetime,timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
from collector.baostock_batch import FIELDS,END
from collector.p2_independent_bars import assess,audit_csv

# Archived originals and quality receipt verified on 2026-10-31.
# Pin this RESEARCH pilot cohort: filling other P1 shards cannot rotate it.
PILOT_SHARD="shard_0098"

def safe_day(now=None):
    clock=now or datetime.now(ZoneInfo("Asia/Shanghai"))
    if clock.tzinfo is None:raise ValueError("naive timestamp")
    bj=clock.astimezone(ZoneInfo("Asia/Shanghai"))
    day=bj.date() if bj.hour>=18 else bj.date()-timedelta(days=1)
    while day.weekday()>=5:day-=timedelta(days=1)
    return day

def baseline_items(root,limit=8):
    if type(limit) is not int or not 1<=limit<=8:raise ValueError("max eight issuers")
    epoch=Path(root)
    try:
        status=json.loads((epoch/"archive_status.json").read_text())
    except (OSError,ValueError) as exc:
        raise ValueError("no archived P1 originals") from exc
    sha=status.get("source_sha256")
    if (not isinstance(sha,str) or not re.fullmatch("[a-f0-9]{64}",sha)
        or epoch.name!=sha[:16] or status.get("trade_gate")!="BLOCKED"):
        raise ValueError("archive epoch provenance mismatch")
    receipt=epoch/PILOT_SHARD/"quality.json"
    if not receipt.is_file():raise ValueError("missing frozen P4 pilot shard")
    receipts=[receipt]
    picked=[]
    seen=set()
    for receipt in receipts:
        verified=assess(receipt.parent)
        for detail in verified["details"]:
            code=detail["code"]
            if code in seen:raise ValueError("duplicate baseline issuer")
            seen.add(code)
            raw=(receipt.parent/(code.replace(".","_")+".csv")).read_bytes()
            rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            if rows[-1]["date"]>END:raise ValueError("frozen baseline extends past cutoff")
            picked.append((code,raw,rows))
            if len(picked)==limit:return picked
    return picked

def crossings(baseline,tail,anchor):
    """Separate chronological 20-tradable-close calculation, no phantom fills."""
    window=deque(maxlen=20)
    above_before=None
    events=[]
    for row in baseline+tail:
        if row["tradestatus"]!="1":
            above_before=None
            continue
        window.append(Decimal(row["close"]))
        if len(window)<20:continue
        above=window[-1]*20>sum(window)
        if row["date"]>anchor and above and above_before is False:
            events.append(row["date"])
        above_before=above
    return events

def run(root,out,bs,as_of=None,limit=8,now=None,archive_commit=None):
    if archive_commit is not None and not re.fullmatch("[0-9a-f]{40}",archive_commit):
        raise ValueError("invalid source archive commit")
    asof=date.fromisoformat(as_of) if as_of else safe_day(now)
    if not date.fromisoformat(END)<asof<=safe_day(now):
        raise ValueError("as-of is not a completed post-baseline day")
    selected=baseline_items(root,limit)
    epoch_sha=json.loads((Path(root)/"archive_status.json").read_text())["source_sha256"]
    if not selected:raise ValueError("empty verified pilot")
    for code,raw,rows in selected:
        if (asof-date.fromisoformat(rows[-1]["date"])).days>90:
            raise ValueError("pilot baseline too old: explicit rebase required")
    dest=Path(out);dest.mkdir(parents=True,exist_ok=True)
    report={"phase":"P4_BOUNDED_CURRENT_TAIL_MA20_RESEARCH",
        "as_of_day":asof.isoformat(),"frozen_p1_end":END,
        "source_archive_commit":archive_commit,
        "source_epoch_sha256":epoch_sha,
        "pilot_shard":PILOT_SHARD,
        "scope":"AT_MOST_EIGHT_ALREADY_ARCHIVED_ISSUERS",
        "selected_codes":[c for c,_,_ in selected],
        "selected_issuers":len(selected),"results":[],
        "non_executable_ma20_crossing_events":[],
        "captured_issuer_count":0,"new_source_rows":0,
        "observations_source_current_certified":False,
        "complete_mainboard_coverage":False,"historical_PIT_verified":False,
        "strategy_buy_signals_certified":0,"entry_fills_assumed":0,
        "returns_computed":False,"trade_gate":"BLOCKED","orders":[],
        "executable_candidates":[],"paid_api_calls":0}
    logged=False
    try:
        session=bs.login()
        if session.error_code!="0":raise ValueError("vendor login unavailable")
        logged=True
        for code,raw,baseline in selected:
            anchor=baseline[-1]["date"]
            entry={"code":code,"anchor_date":anchor,
                "baseline_sha256":hashlib.sha256(raw).hexdigest(),
                "status":"UNAVAILABLE"}
            try:
                query=bs.query_history_k_data_plus(code,fields=",".join(FIELDS),
                    start_date=anchor,end_date=asof.isoformat(),
                    frequency="d",adjustflag="3")
                if query.error_code!="0" or list(query.fields)!=FIELDS:
                    raise ValueError("wrong provider schema or error")
                values=[]
                while query.next():
                    row=query.get_row_data()
                    if len(row)!=len(FIELDS):raise ValueError("malformed source row")
                    values.append(row)
                    if len(values)>100:raise ValueError("unbounded vendor response")
                if not values:raise ValueError("missing baseline anchor")
                tail_raw=(",".join(FIELDS)+"\n"+
                          "".join(",".join(row)+"\n" for row in values)).encode()
                stats=audit_csv(tail_raw,code)
                if stats["first"]!=anchor or stats["last"]!=asof.isoformat():
                    raise ValueError("missing overlap or stale research as-of close")
                source_rows=list(csv.DictReader(tail_raw.decode().splitlines()))
                if source_rows[0]!=baseline[-1]:
                    raise ValueError("immutable source anchor differs from provider")
                fresh=source_rows[1:]
                signals=crossings(baseline,fresh,anchor)
                filename=code.replace(".","_")+"_current.csv"
                (dest/filename).write_bytes(tail_raw)
                entry.update(status="OBSERVED_RESEARCH_ONLY",filename=filename,
                    tail_sha256=hashlib.sha256(tail_raw).hexdigest(),
                    observed_last_date=stats["last"],fresh_rows=len(fresh),
                    crossing_days=signals)
                report["captured_issuer_count"]+=1
                report["new_source_rows"]+=len(fresh)
                report["non_executable_ma20_crossing_events"].extend(
                    {"code":code,"completed_close_day":d,
                     "signal_known_after_close_only":True,
                     "entry_filled":False} for d in signals)
            except (ValueError,KeyError,TypeError,UnicodeError) as exc:
                entry["error_type"]=type(exc).__name__
            report["results"].append(entry)
    except (ValueError,TypeError,OSError) as exc:
        report["session_error_type"]=type(exc).__name__
    finally:
        if logged:
            try:bs.logout()
            except Exception:pass
    report["status"]=("OBSERVED_BOUNDED_RESEARCH" if report["captured_issuer_count"]==len(selected)
                      else "BLOCKED_PARTIAL")
    (dest/"current_tail_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("results","non_executable_ma20_crossing_events")}))
    return report

def verify(root,out):
    folder=Path(out)
    report=json.loads((folder/"current_tail_report.json").read_text())
    if (report.get("trade_gate")!="BLOCKED" or report.get("orders")!=[]
        or report.get("executable_candidates")!=[]
        or report.get("strategy_buy_signals_certified")!=0
        or report.get("complete_mainboard_coverage") is not False
        or report.get("historical_PIT_verified") is not False
        or report.get("pilot_shard")!=PILOT_SHARD
        or report.get("status")!="OBSERVED_BOUNDED_RESEARCH"):
        raise ValueError("unsafe or incomplete research capture")
    if not re.fullmatch("[0-9]{4}-[0-9]{2}-[0-9]{2}",str(report.get("as_of_day",""))):
        raise ValueError("missing research as-of date")
    if report.get("source_epoch_sha256")!=json.loads((Path(root)/"archive_status.json").read_text())["source_sha256"]:
        raise ValueError("source epoch changed")
    selected=baseline_items(root,len(report["selected_codes"]))
    if [x[0] for x in selected]!=report["selected_codes"]:
        raise ValueError("baseline membership changed")
    if len(report["results"])!=len(selected) or report["captured_issuer_count"]!=len(selected):
        raise ValueError("incomplete issuer receipts")
    events=[];new_rows=0
    for (code,raw,baseline),item in zip(selected,report["results"]):
        filename=code.replace(".","_")+"_current.csv"
        if item.get("code")!=code or item.get("filename")!=filename or item.get("status")!="OBSERVED_RESEARCH_ONLY":
            raise ValueError("issuer receipt mismatch")
        content=(folder/filename).read_bytes()
        if (hashlib.sha256(raw).hexdigest()!=item.get("baseline_sha256")
            or hashlib.sha256(content).hexdigest()!=item.get("tail_sha256")):
            raise ValueError("source hash mismatch")
        stats=audit_csv(content,code)
        rows=list(csv.DictReader(content.decode("utf-8-sig").splitlines()))
        anchor=baseline[-1]["date"]
        if (rows[0]!=baseline[-1] or item.get("anchor_date")!=anchor
            or stats["last"]!=item.get("observed_last_date")
            or stats["last"]!=report["as_of_day"]
            or item.get("fresh_rows")!=len(rows)-1):
            raise ValueError("overlap, date or row-count mismatch")
        signal_days=crossings(baseline,rows[1:],anchor)
        if signal_days!=item.get("crossing_days"):
            raise ValueError("truncated or forged per-issuer MA20 events")
        events.extend({"code":code,"completed_close_day":d,
                       "signal_known_after_close_only":True,
                       "entry_filled":False} for d in signal_days)
        new_rows+=len(rows)-1
    if (events!=report["non_executable_ma20_crossing_events"]
        or new_rows!=report["new_source_rows"]):
        raise ValueError("incomplete or altered full research event set")
    return {"phase":"P4_CURRENT_TAIL_INDEPENDENT_REPLAY",
        "verified_issuers":len(selected),"new_rows_verified":new_rows,
        "verified_non_executable_crossings":len(events),
        "as_of_day":report["as_of_day"],"complete_mainboard_coverage":False,
        "historical_PIT_verified":False,"buy_signals_authorized":0,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("capture","verify"),required=True)
    p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    p.add_argument("--as-of");p.add_argument("--archive-commit")
    a=p.parse_args()
    if a.mode=="capture":
        import baostock as bs
        result=run(a.root,a.out,bs,as_of=a.as_of,archive_commit=a.archive_commit)
        if result["status"]!="OBSERVED_BOUNDED_RESEARCH":
            raise SystemExit(2)
    else:
        result=verify(a.root,a.out)
        print(json.dumps(result))
if __name__=="__main__":main()
