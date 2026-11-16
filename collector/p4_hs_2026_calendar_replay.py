"""Compare announced 2026 SSE/SZSE sessions with archived vendor dates, research only."""
import argparse
from datetime import date, timedelta
import csv
import json
from pathlib import Path

from collector.p2_independent_bars import assess
from collector.p4_sse_holiday_crosscheck import OFFICIAL_SSE_NOTICES, closures

SZSE_NOTICE = "https://www.szse.cn/disclosure/notice/t20251222_618087.html"
# Transcribed independently from the SZSE annual circular, not inferred from bars.
SZSE_2026 = ((1, 1, 1, 3), (2, 15, 2, 23), (4, 4, 4, 6), (5, 1, 5, 5),
             (6, 19, 6, 21), (9, 25, 9, 27), (10, 1, 10, 7))


def days(first, last):
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def reconcile(observed, first, last):
    if first.year != 2026 or last.year != 2026 or first > last:
        raise ValueError("expected an ordered window within notice year 2026")
    spans = {"sh": closures(2026),
             "sz": {day for sm, sd, em, ed in SZSE_2026
                    for day in days(date(2026, sm, sd), date(2026, em, ed))}}
    result = {}
    for exchange, closed in spans.items():
        expected = {d for d in days(first, last) if d.weekday() < 5 and d not in closed}
        seen = {d for d in observed[exchange] if first <= d <= last}
        result[exchange] = dict(expected=len(expected), observed=len(seen),
                                missing=sorted(d.isoformat() for d in expected - seen),
                                unexpected=sorted(d.isoformat() for d in seen - expected))
    return dict(scope="ANNUAL_NOTICE_VS_AGGREGATE_VENDOR_DATES",
                start=first.isoformat(), end=last.isoformat(),
                published_holiday_ranges_agree=spans["sh"] == spans["sz"],
                sources={"sh": OFFICIAL_SSE_NOTICES[2026], "sz": SZSE_NOTICE},
                venues=result, official_notices_fetched_in_this_run=False,
                historical_PIT_verified=False, official_calendar_fully_verified=False,
                trade_gate="BLOCKED", orders=[], executable_candidates=[])


# Independently transcribed follow-up notices, not inferred from vendor dates.
FOLLOWUP = {
    "sh": ("https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml",
           "2026-09-17", (("2026-09-25", "2026-09-27", "2026-09-28"),
                          ("2026-10-01", "2026-10-07", "2026-10-08")),
           ("2026-09-20", "2026-10-10")),
    "sz": ("https://www.szse.cn/www/disclosure/notice/general/t20260917_622911.html",
           "2026-09-17", (("2026-09-25", "2026-09-27", "2026-09-28"),
                          ("2026-10-01", "2026-10-07", "2026-10-08")),
           ("2026-09-20", "2026-10-10")),
}


def reconcile_followup(observed):
    venues = {}
    for market, (url, published, periods, weekends) in FOLLOWUP.items():
        source_ranges = closures(2026) if market == "sh" else {
            d for sm, sd, em, ed in SZSE_2026 for d in days(date(2026, sm, sd), date(2026, em, ed))}
        holiday_days = set()
        reopens = set()
        publication_day = date.fromisoformat(published)
        for start, end, reopen in periods:
            begin, finish, nxt = map(date.fromisoformat, (start, end, reopen))
            interval = set(days(begin, finish))
            if (not publication_day < begin <= finish < nxt or not interval <= source_ranges
                    or nxt in source_ranges or nxt.weekday() >= 5
                    or any(d.weekday() < 5 and d not in source_ranges
                           for d in days(finish + timedelta(days=1), nxt - timedelta(days=1)))):
                raise ValueError("holiday follow-up conflicts with annual notice")
            holiday_days.update(interval)
            reopens.add(nxt)
        weekend_days = {date.fromisoformat(d) for d in weekends}
        if any(d.weekday() < 5 for d in weekend_days):
            raise ValueError("follow-up weekend is not a weekend")
        present = observed[market]
        venues[market] = {
            "notice_url": url, "notice_display_date": published,
            "display_date_precedes_closures": True,
            "closed_dates_in_vendor_rows": sorted(d.isoformat() for d in (holiday_days | weekend_days) & present),
            "reopen_dates_observed": sorted(d.isoformat() for d in reopens & present),
            "reopen_dates_missing": sorted(d.isoformat() for d in reopens - present),
        }
    return {"venues": venues, "first_publication_clock_verified": False,
            "all_exceptional_closures_reviewed": False}


def replay(epoch):
    observed = {"sh": set(), "sz": set()}
    shards = sorted(epoch.glob("shard_*/quality.json"))
    if not shards:
        raise ValueError("no original archive shards")
    for receipt in shards:
        for item in assess(receipt.parent)["details"]:
            code = item["code"]
            raw = receipt.parent / (code.replace(".", "_") + ".csv")
            with raw.open(encoding="utf-8-sig", newline="") as stream:
                observed[code[:2]].update(date.fromisoformat(row["date"]) for row in csv.DictReader(stream))
    return observed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epoch", type=Path, required=True)
    p.add_argument("--start", type=date.fromisoformat, default=date(2026, 1, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 20))
    a = p.parse_args()
    observed = replay(a.epoch)
    report = reconcile(observed, a.start, a.end)
    if a.start <= date(2026, 9, 20) and a.end >= date(2026, 10, 10):
        report["mid_autumn_national_day_followup"] = reconcile_followup(observed)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
