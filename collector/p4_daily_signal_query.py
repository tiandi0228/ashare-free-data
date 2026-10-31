"""Read-only, date-scoped P4 MA20 research signal ledger from permanent source bytes.

No stale/missing captured date can be interpreted as zero market signals.
Every archived run is independently replayed before counting any observation.
"""
import argparse,csv,json,re
from datetime import date,timedelta
from pathlib import Path
from collector.baostock_batch import END
from collector.p4_current_tail_permanent_archive import readback

RUN_DIR=re.compile(r"run_([1-9][0-9]*)_attempt_([1-9][0-9]*)\Z")

def query(archive_root,epoch,start,end=None):
    first=date.fromisoformat(start)
    last=date.fromisoformat(end or start)
    if first<=date.fromisoformat(END) or last<first or (last-first).days>=31:
        raise ValueError("research query requires 1 to 31 days after frozen P1 end")
    epoch=Path(epoch)
    status=json.loads((epoch/"archive_status.json").read_text())
    epoch_sha=status.get("source_sha256")
    if (not isinstance(epoch_sha,str) or not re.fullmatch("[a-f0-9]{64}",epoch_sha)
        or epoch.name!=epoch_sha[:16] or status.get("trade_gate")!="BLOCKED"):
        raise ValueError("untrusted original archive epoch")
    location=Path(archive_root)/"p4-current-tail"/epoch_sha[:16]
    observed={}   # (day, issuer) -> exact audited vendor row and crossing verdict
    runs=[]
    registered_codes=set()
    for folder in sorted(location.iterdir()) if location.exists() else []:
        if not folder.is_dir() or not RUN_DIR.fullmatch(folder.name):
            raise ValueError("unexpected archived P4 run object")
        match=RUN_DIR.fullmatch(folder.name)
        rid,attempt=map(int,match.groups())
        receipt=json.loads((folder/"permanent_receipt.json").read_text())
        pin=receipt.get("source_archive_commit")
        if (not isinstance(pin,str) or not re.fullmatch("[0-9a-f]{40}",pin)
            or receipt.get("github_run_id")!=rid
            or receipt.get("github_run_attempt")!=attempt
            or receipt.get("source_epoch_sha256")!=epoch_sha):
            raise ValueError("archived current-tail provenance mismatch")
        certified=readback(archive_root,epoch,rid,attempt,pin)
        if certified.get("trade_gate")!="BLOCKED" or certified.get("orders")!=[]:
            raise ValueError("unsafe archived current-tail readback")
        report=json.loads((folder/"current_tail_report.json").read_text())
        as_of=date.fromisoformat(report["as_of_day"])
        codes=report["selected_codes"]
        registered_codes.update(codes)
        run={"github_run_id":rid,"attempt":attempt,"as_of_day":as_of.isoformat(),
             "archive_source_commit":pin,"observed_issuers":len(codes)}
        runs.append(run)
        for code in codes:
            filename=code.replace(".","_")+"_current.csv"
            raw=(folder/filename).read_text(encoding="utf-8-sig")
            rows=list(csv.DictReader(raw.splitlines()))
            crossings=set(next(x for x in report["results"]
                                if x["code"]==code)["crossing_days"])
            for row in rows[1:]:   # first row is the frozen P1 anchor, not a daily update
                day=date.fromisoformat(row["date"])
                if day<first or day>last:
                    continue
                if day>as_of or row["tradestatus"] not in ("0","1"):
                    raise ValueError("future or invalid archived vendor day")
                key=(day.isoformat(),code)
                value={"source_row":tuple(row[f] for f in row),
                       "fresh_ma20_crossing_after_close":day.isoformat() in crossings}
                if key in observed and observed[key]!=value:
                    raise ValueError("conflicting immutable vendor evidence for research day")
                observed[key]=value
    summaries=[]
    events=[]
    day=first
    while day<=last:
        d=day.isoformat()
        issuers=sorted(code for (dt,code) in observed if dt==d)
        day_events=sorted(code for code in issuers
                          if observed[(d,code)]["fresh_ma20_crossing_after_close"])
        for code in day_events:
            events.append({"code":code,"completed_close_day":d,
                           "signal_known_after_close_only":True,
                           "entry_filled":False})
        if not issuers:
            state="NO_VERIFIED_VENDOR_ROWS_FOR_DAY"
            count=None  # Important: missing data must not silently mean zero signals.
        elif len(issuers)!=len(registered_codes):
            state="PARTIAL_BOUNDED_ISSUER_COVERAGE"
            count=len(day_events)
        else:
            state="VERIFIED_BOUNDED_PILOT_DAY"
            count=len(day_events)
        summaries.append({"date":d,"status":state,
                          "observed_issuer_count":len(issuers),
                          "expected_bounded_issuer_count":len(registered_codes),
                          "observed_non_executable_crossing_count":count,
                          "codes_with_crossing":day_events})
        day+=timedelta(days=1)
    return {"phase":"P4_DURABLE_DAILY_RESEARCH_SIGNAL_QUERY",
            "start_day":first.isoformat(),"end_day":last.isoformat(),
            "permanent_source_epoch_sha256":epoch_sha,
            "verified_archive_runs":len(runs),"archived_run_provenance":runs,
            "observed_bounded_issuer_universe":sorted(registered_codes),
            "days":summaries,
            "observed_non_executable_crossings":events,
            "missing_days_are_not_zero_signals":True,
            "full_market_scan_performed":False,
            "complete_mainboard_coverage":False,
            "historical_PIT_verified":False,
            "strategy_buy_signals_authorized":0,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True)
    p.add_argument("--epoch",required=True)
    p.add_argument("--start",required=True)
    p.add_argument("--end")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=query(a.archive_root,a.epoch,a.start,a.end)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"phase":result["phase"],
                      "archive_runs":result["verified_archive_runs"],
                      "days":result["days"],"trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":
    main()
