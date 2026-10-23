"""Independent SSE holiday-notice cross-check; closure notices are not full PIT calendar certificates."""
import argparse,csv,json
from datetime import date,timedelta
from pathlib import Path
from collector.p2_independent_bars import assess

OFFICIAL_SSE_NOTICES={
  2025:"https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml",
  2026:"https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml",
}
# Ranges from annual exchange closure notices. Weekend closures are checked separately.
HOLIDAY_RANGES={
  2025:[("2025-01-01","2025-01-01"),("2025-01-28","2025-02-04"),
        ("2025-04-04","2025-04-06"),("2025-05-01","2025-05-05"),
        ("2025-05-31","2025-06-02"),("2025-10-01","2025-10-08")],
  2026:[("2026-01-01","2026-01-03"),("2026-02-15","2026-02-23"),
        ("2026-04-04","2026-04-06"),("2026-05-01","2026-05-05"),
        ("2026-06-19","2026-06-21"),("2026-09-25","2026-09-27"),
        ("2026-10-01","2026-10-07")],
}
def closures(year):
    if year not in HOLIDAY_RANGES:raise ValueError("no official holiday notice coverage")
    result=set()
    for first,last in HOLIDAY_RANGES[year]:
        d=date.fromisoformat(first);end=date.fromisoformat(last)
        while d<=end:
            result.add(d);d+=timedelta(days=1)
    return result
def check_dates(days):
    if not days:raise ValueError("no historical dates")
    dates=sorted(set(days))
    unsupported=sorted({d.year for d in dates}-set(HOLIDAY_RANGES))
    supported=[d for d in dates if d.year in HOLIDAY_RANGES]
    if not supported:raise ValueError("no official notice-covered dates")
    dates=supported
    closed=set().union(*(closures(y) for y in {d.year for d in dates}))
    bad_weekends=[d.isoformat() for d in dates if d.weekday()>=5]
    bad_holidays=[d.isoformat() for d in dates if d in closed]
    expected=[];day=dates[0]
    while day<=dates[-1]:
        if day.weekday()<5 and day not in closed:expected.append(day)
        day+=timedelta(days=1)
    missing=sorted(set(expected)-set(dates))
    return {"date_count":len(dates),"unsupported_years":unsupported,
            "uncovered_source_dates":len(set(days)-set(dates)),
            "unexpected_weekend_dates":bad_weekends,
            "unexpected_holiday_dates":bad_holidays,
            "missing_expected_weekdays":[d.isoformat() for d in missing],
            "expected_weekdays_excluding_official_closures":len(expected),
            "official_sse_closure_notice_urls":[OFFICIAL_SSE_NOTICES[y] for y in sorted({d.year for d in dates})],
            "official_notices_fetched_in_this_run":False,
            "historical_exchange_calendar_authenticated":False}
def audit(root):
    receipts=sorted(Path(root).glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("no archived source receipts")
    dates=set();issuers=0
    for p in receipts:
        result=assess(p.parent)
        for item in result["details"]:
            issuers+=1
            raw=(p.parent/(item["code"].replace(".","_")+".csv")).read_text(encoding="utf-8-sig")
            dates.update(date.fromisoformat(row["date"]) for row in csv.DictReader(raw.splitlines()))
    data=check_dates(dates)
    return {"phase":"P4_SSE_NOTICE_INDEPENDENT_DATE_CHECK","verified_issuers":issuers,**data,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=audit(a.root);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if not isinstance(v,list) or len(v)<15},ensure_ascii=False))
if __name__=="__main__":main()
