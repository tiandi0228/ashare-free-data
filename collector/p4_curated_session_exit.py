"""Research-only session offsets from curated SSE closure notices.

Not a certified SZSE/SSE complete exchange calendar, and never authorizes fills.
"""
from datetime import date,timedelta
from collector.p4_sse_holiday_crosscheck import HOLIDAY_RANGES,closures

def sessions_between(first,last):
    start=date.fromisoformat(first);end=date.fromisoformat(last)
    if end<start:raise ValueError("reversed date interval")
    years=set(range(start.year,end.year+1))
    if not years.issubset(HOLIDAY_RANGES):raise ValueError("uncurated year")
    closed=set().union(*(closures(y) for y in years))
    days=[];d=start
    while d<=end:
        if d.weekday()<5 and d not in closed:days.append(d.isoformat())
        d+=timedelta(days=1)
    return days

def research_exit(entry_day,day_three_calendar=None):
    start=date.fromisoformat(entry_day)
    if start.year not in HOLIDAY_RANGES:raise ValueError("uncurated entry year")
    days=sessions_between(entry_day,(start+timedelta(days=45)).isoformat())
    if not days or days[0]!=entry_day:raise ValueError("entry is not candidate session")
    if len(days)<4:raise ValueError("incomplete third session")
    third=days[3]
    friday=next((day for day in days[1:] if date.fromisoformat(day).weekday()==4),None)
    if friday is None:raise ValueError("no prospective Friday session")
    chosen=min(third,friday)
    return {"phase":"P4_CURATED_SESSION_EXIT_RESEARCH","entry":entry_day,
            "candidate_D_plus_3_session":third,"candidate_friday_exit":friday,
            "candidate_earlier_exit":chosen,
            "days_after_entry":days[1:4],"calendar_is_officially_authenticated":False,
            "issuer_halt_status_authenticated":False,"order_fills_verified":0,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
