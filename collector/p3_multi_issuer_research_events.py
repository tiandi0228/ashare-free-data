"""Multi-issuer strict research-event intake. Unverified sources never become trading states."""
from datetime import date
import re

CODE=re.compile(r"^(sh\.(?:600|601|603|605)[0-9]{3}|sz\.(?:000|001|002|003)[0-9]{3})$")
SHA=re.compile(r"^[a-f0-9]{64}$")
ALLOWED={"ISSUER_STATEMENT","ISSUER_FORECAST","UNVERIFIED_REFERENCE"}
def merge_research_ledgers(ledgers):
    if not isinstance(ledgers,list) or not ledgers:
        raise ValueError("no source ledgers")
    out=[];seen=set()
    for ledger in ledgers:
        if not isinstance(ledger,dict) or ledger.get("trade_gate")!="BLOCKED" or ledger.get("orders")!=[] or ledger.get("executable_candidates")!=[]:
            raise ValueError("unsafe source ledger")
        if ledger.get("historical_pit_states_verified") is not False or ledger.get("confirmed_exchange_effective_event_count")!=0:
            raise ValueError("source falsely certified")
        rows=ledger.get("rows")
        if not isinstance(rows,list) or ledger.get("row_count")!=len(rows):
            raise ValueError("source row count mismatch")
        for row in rows:
            issuer=row.get("issuer")
            if not isinstance(issuer,str) or CODE.fullmatch(issuer) is None:
                raise ValueError("non-mainboard issuer")
            if row.get("date_semantics") not in ALLOWED or row.get("research_only") is not True:
                raise ValueError("untrusted event semantics")
            if row.get("confirmed_effective_date") is not None or row.get("historical_publication_instant") is not None or row.get("tradability_state_asof") is not None or row.get("eligible_for_historical_universe") is not False:
                raise ValueError("unverified event falsely promoted")
            day=row.get("mentioned_calendar_date")
            if type(day) is not str or date.fromisoformat(day).isoformat()!=day:
                raise ValueError("invalid event date")
            hashes=row.get("source_sha256_receipts")
            if not isinstance(hashes,list) or any(not isinstance(s,str) or SHA.fullmatch(s) is None for s in hashes):
                raise ValueError("invalid sha receipts")
            if row["date_semantics"]=="UNVERIFIED_REFERENCE" and hashes:
                raise ValueError("reference cannot inherit original hashes")
            key=(issuer,row.get("event_kind"),day,row["date_semantics"])
            if key in seen:raise ValueError("duplicate event across ledgers")
            seen.add(key)
            out.append(dict(row))
    out.sort(key=lambda e:(e["mentioned_calendar_date"],e["issuer"],str(e["event_kind"])))
    return {"phase":"P3_MULTI_ISSUER_RESEARCH_EVENTS","issuer_count":len({x["issuer"] for x in out}),
            "event_count":len(out),"rows":out,"confirmed_effective_event_count":0,
            "historical_pit_states_verified":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
