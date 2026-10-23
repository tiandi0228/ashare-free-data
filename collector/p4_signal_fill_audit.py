"""P4 historical signal/fill chronology audit; never fabricates orders or returns."""
from datetime import datetime,timezone

def parse(t):
    d=datetime.fromisoformat(t.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:raise ValueError("timestamps must have timezone")
    return d.astimezone(timezone.utc)

def assess(signals):
    if not isinstance(signals,list):raise ValueError("signal list required")
    examined=filled=unfilled=0;records=[]
    for s in signals:
        if s.get("trade_gate")!="BLOCKED" or s.get("orders")!=[]:
            raise ValueError("research boundary violated")
        signal=parse(s["signal_completed_at"])
        if parse(s["source_observed_at"])>signal:raise ValueError("lookahead source")
        if s.get("execution_status") not in ("UNFILLED","FILLED"):raise ValueError("unknown status")
        examined+=1
        if s["execution_status"]=="UNFILLED":
            if s.get("fill") is not None:raise ValueError("unfilled signal has a fill")
            unfilled+=1
            records.append({"signal_id":s["signal_id"],"status":"UNFILLED","return_included":False})
        else:
            f=s.get("fill")
            if not isinstance(f,dict) or not f.get("independent_execution_receipt_sha256"):
                raise ValueError("fill must have external evidence")
            if parse(f["filled_at"])<=signal:raise ValueError("fill at or before completed signal")
            if len(f["independent_execution_receipt_sha256"])!=64:raise ValueError("invalid receipt hash")
            filled+=1
            records.append({"signal_id":s["signal_id"],"status":"FILL_RECEIPT_PRESENT_UNVERIFIED","return_included":False})
    return {"phase":"P4_SIGNAL_FILL_TEMPORAL_AUDIT","signal_count":examined,
            "fill_evidence_count":filled,"unfilled_signal_count":unfilled,
            "signal_fill_evidence_rate":(filled/examined if examined else None),
            "returns_computed":False,"historical_OOS_validated":False,
            "records":records,"trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
