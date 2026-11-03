"""Conservative expected minute-label audit for CN A-share research snapshots.

Minute labels are assumed to include 09:30..11:30 and 13:00..15:00 inclusive
for *audit only*. Vendors can label the final/opening bar differently.
Never use this calculation alone to certify complete data or enable trades.
"""
import datetime as dt

SESSION_BOUNDS=((dt.time(9,30),dt.time(11,30)),
                (dt.time(13,0),dt.time(15,0)))

def expected_minute_labels(day, now):
    """Expected labels whose nominal minute has ended as of now."""
    if now.tzinfo is None or now.date()!=day:
        raise ValueError("audit requires timezone-aware same-day clock")
    cutoff=now.replace(second=0,microsecond=0)
    result=[]
    for start,end in SESSION_BOUNDS:
        stamp=dt.datetime.combine(day,start,tzinfo=now.tzinfo)
        stop=dt.datetime.combine(day,end,tzinfo=now.tzinfo)
        while stamp<=stop:
            if stamp<cutoff:result.append(stamp)
            stamp+=dt.timedelta(minutes=1)
    return result

def audit_minute_coverage(stamps, now):
    """Return evidence counts only; NEVER declare data complete."""
    if not stamps:raise ValueError("missing source bars")
    expected=expected_minute_labels(now.date(),now)
    expected_set=set(expected)
    observed_set=set(stamps)
    floor=now.replace(second=0,microsecond=0)
    future=sorted(x for x in observed_set if x>floor)
    forming=sorted(x for x in observed_set if x==floor)
    covered=sorted(x for x in expected_set if x in observed_set)
    missing=sorted(expected_set-observed_set)
    missing_iso=[x.isoformat() for x in missing]
    # This is an expected-label ratio, not a vendor-certified completeness value.
    return {
        "convention":"ASSUMED_CN_STOCK_MINUTE_LABELS_INCLUSIVE",
        "expected_completed_labels":len(expected),
        "covered_expected_completed_labels":len(covered),
        "missing_expected_completed_labels":len(missing),
        "coverage_ratio_observed":round(len(covered)/len(expected),6) if expected else None,
        "missing_labels":missing_iso,
        "forming_labels":[x.isoformat() for x in forming],
        "future_labels":[x.isoformat() for x in future],
        "source_has_future_labels":bool(future),
        "minute_data_complete_certified":False,
        "limitations":[
            "UNOFFICIAL_VENDOR_LABEL_CONVENTION_NOT_INDEPENDENTLY_VERIFIED",
            "NOT_A_POINT_IN_TIME_COMPLETE_MINUTE_RECORD",
            "NOT_AN_EXECUTABLE_TRADING_QUOTE",
        ],
    }
