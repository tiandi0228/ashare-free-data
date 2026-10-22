"""Conservative first-observed boundary for real publicly retrieved source receipts.

A 2026-10-22 first retrieval cannot independently prove the source was
accessible at an earlier trading decision. This module never backdates data.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

def observe(issuer_receipt, exchange_receipt):
    rows=[]
    for publisher, receipt, time_key, docs_key, day_key in (
        ("CNINFO",issuer_receipt,"observed_utc","sources","date"),
        ("SSE",exchange_receipt,"captured_at_utc","pages","document_date"),
    ):
        timestamp=receipt.get(time_key)
        if not isinstance(timestamp,str) or not timestamp.endswith("Z"):
            raise ValueError("missing UTC retrieval time")
        instant=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
        if instant.tzinfo is None:
            raise ValueError("unqualified retrieval time")
        for doc in receipt.get(docs_key,[]):
            day=doc.get(day_key)
            if not isinstance(day,str):
                raise ValueError("missing document day")
            from datetime import date
            doc_day=date.fromisoformat(day)
            observed_day=instant.astimezone(SHANGHAI).date()
            if doc_day>observed_day:
                raise ValueError("document claims future relative to observed capture")
            rows.append({
                "publisher":publisher,
                "document_day":day,
                "first_capture_proven_no_earlier_than_utc":timestamp,
                "earlier_asof_availability_proven":False,
                "issuer_day_tradability_proven":False
            })
    if len(rows)!=4:
        raise ValueError("expected four bounded original documents")
    return {
        "phase":"P3_RETRIEVAL_TIME_VS_HISTORICAL_AVAILABILITY",
        "documents":rows,
        "document_count":len(rows),
        "historical_availability_verified":False,
        "first_observed_does_not_prove_first_publication":True,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
