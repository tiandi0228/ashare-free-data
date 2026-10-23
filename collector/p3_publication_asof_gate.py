"""P3 immutable publication/effective-time boundary audit (research, NO TRADES).

An official PDF with an effective date does not prove the market knew it then.
Require independently authenticated first-publication instant, not scrape time.
"""
from datetime import datetime,date,timezone
import re
from zoneinfo import ZoneInfo

SHA=re.compile(r"[0-9a-f]{64}\Z")

def instant(value):
    if not isinstance(value,str):raise ValueError("timestamp missing")
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError("unauthenticated timezone")
    return t.astimezone(timezone.utc)

def assess(events, decision_instant):
    asof=instant(decision_instant)
    if not isinstance(events,list):raise ValueError("event inventory missing")
    results=[];seen=set()
    for e in events:
        if e.get("trade_gate")!="BLOCKED" or e.get("orders")!=[]:
            raise ValueError("upstream risk boundary violated")
        key=(e.get("issuer"),e.get("kind"),e.get("original_sha256"))
        if key in seen:raise ValueError("duplicate event provenance")
        seen.add(key)
        digest=e.get("original_sha256")
        if not isinstance(digest,str) or not SHA.fullmatch(digest):raise ValueError("invalid original SHA")
        effective=date.fromisoformat(e["effective_date"])
        published=e.get("authenticated_first_published_at")
        attested=(e.get("publisher_independently_authenticated") is True and
                  e.get("original_bytes_verified") is True and
                  e.get("publication_timestamp_independently_authenticated") is True)
        if attested and published is None:raise ValueError("authenticated publication missing")
        published_at=instant(published) if published is not None else None
        known=bool(attested and published_at<=asof)
        effective_at_asof=bool(known and effective<=asof.astimezone(ZoneInfo('Asia/Shanghai')).date())
        results.append({"issuer":e["issuer"],"kind":e["kind"],
                        "effective_date":effective.isoformat(),
                        "known_before_decision":known,
                        "effective_by_decision_date":effective_at_asof,
                        "certified_full_daily_state":False,
                        "original_sha256":digest})
    return {"phase":"P3_EVENT_PUBLICATION_ASOF_BOUNDARY",
            "decision_instant_utc":asof.isoformat(),
            "events":results,
            "known_event_count":sum(r["known_before_decision"] for r in results),
            "complete_historical_risk_state":False,
            "eligible_for_trading":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
