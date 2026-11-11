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
    if not isinstance(events,list) or len(events)>10000:raise ValueError("event inventory missing or unbounded")
    results=[];seen=set()
    for e in events:
        if not isinstance(e,dict):raise ValueError("malformed event row")
        if (not isinstance(e.get("issuer"),str) or not e["issuer"].strip()
            or not isinstance(e.get("kind"),str) or not e["kind"].strip()):
            raise ValueError("event issuer or kind missing")
        if e.get("trade_gate")!="BLOCKED" or e.get("orders")!=[] or e.get("executable_candidates",[])!=[]:
            raise ValueError("upstream risk boundary violated")
        key=(e.get("issuer"),e.get("kind"),e.get("original_sha256"),e.get("effective_date"))
        if key in seen:raise ValueError("duplicate event provenance")
        seen.add(key)
        digest=e.get("original_sha256")
        if not isinstance(digest,str) or not SHA.fullmatch(digest):raise ValueError("invalid original SHA")
        effective_str=e.get("effective_date")
        if not isinstance(effective_str,str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",effective_str):
            raise ValueError("invalid ISO effective date")
        effective=date.fromisoformat(effective_str)
        published=e.get("authenticated_first_published_at")
        attested=(e.get("publisher_independently_authenticated") is True and
                  e.get("original_bytes_verified") is True and
                  e.get("publication_timestamp_independently_authenticated") is True)
        if attested and published is None:raise ValueError("authenticated publication missing")
        published_at=instant(published) if published is not None else None
        # Evidence triage is descriptive only; none of these categories
        # certifies a full historical security state or authorizes trading.
        if e.get("original_bytes_verified") is not True:
            gap="ORIGINAL_BYTES_NOT_VERIFIED"
        elif e.get("publisher_independently_authenticated") is not True:
            gap="PUBLISHER_NOT_AUTHENTICATED"
        elif e.get("publication_timestamp_independently_authenticated") is not True:
            gap="FIRST_PUBLICATION_NOT_AUTHENTICATED"
        elif published_at is None:
            raise ValueError("authenticated publication missing")
        elif published_at>asof:
            gap="PUBLICATION_AFTER_DECISION"
        elif effective>asof.astimezone(ZoneInfo('Asia/Shanghai')).date():
            gap="EFFECTIVE_DATE_AFTER_DECISION"
        else:
            gap="EVENT_KNOWN_FULL_DAILY_STATE_UNCERTIFIED"
        known=bool(attested and published_at<=asof)
        effective_at_asof=bool(known and effective<=asof.astimezone(ZoneInfo('Asia/Shanghai')).date())
        results.append({"issuer":e["issuer"],"kind":e["kind"],
                        "effective_date":effective.isoformat(),
                        "known_before_decision":known,
                        "effective_by_decision_date":effective_at_asof,
                        "certified_full_daily_state":False,
                        "publication_proof_status":gap,
                        "original_sha256":digest})
    proof_status_counts={}
    for row in results:
        status=row["publication_proof_status"]
        proof_status_counts[status]=proof_status_counts.get(status,0)+1
    return {"phase":"P3_EVENT_PUBLICATION_ASOF_BOUNDARY",
            "decision_instant_utc":asof.isoformat(),
            "events":results,
            "known_event_count":sum(r["known_before_decision"] for r in results),
            "publication_proof_status_counts":dict(sorted(proof_status_counts.items())),
            "complete_historical_risk_state":False,
            "eligible_for_trading":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
