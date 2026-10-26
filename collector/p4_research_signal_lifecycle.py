"""Deterministic no-trade V2.2 research signal lifecycle; never infers fills."""
from datetime import date
import re

SHA=re.compile(r"[a-f0-9]{64}\Z")
def advance(*,state,event,decision_day,observation_day,receipt_sha256=None):
    if state not in ("SIGNAL_READY","UNFILLED","ENTRY_EVIDENCED","EXIT_EVIDENCED"):
        raise ValueError("invalid research state")
    if event not in ("EXPIRE_UNFILLED","OBSERVE_ENTRY","OBSERVE_EXIT"):
        raise ValueError("invalid transition event")
    start=date.fromisoformat(decision_day);observed=date.fromisoformat(observation_day)
    if observed<start:raise ValueError("observation predates decision")
    if event=="EXPIRE_UNFILLED":
        if state!="SIGNAL_READY" or receipt_sha256 is not None:raise ValueError("invalid unfilled expiry")
        new="UNFILLED"
    elif event=="OBSERVE_ENTRY":
        if state!="SIGNAL_READY" or observed<=start or not isinstance(receipt_sha256,str) or not SHA.fullmatch(receipt_sha256):
            raise ValueError("entry needs later independently evidenced observation")
        new="ENTRY_EVIDENCED"
    else:
        if state!="ENTRY_EVIDENCED" or observed<=start or not isinstance(receipt_sha256,str) or not SHA.fullmatch(receipt_sha256):
            raise ValueError("exit needs independent later receipt")
        new="EXIT_EVIDENCED"
    return {"phase":"P4_V22_RESEARCH_SIGNAL_LIFECYCLE","from_state":state,
            "to_state":new,"event":event,"decision_day":decision_day,"observation_day":observation_day,
            "receipt_present_unverified":receipt_sha256 is not None,
            "filled_trade_certified":False,"net_returns_computed":False,
            "historical_OOS_validated":False,"trade_gate":"BLOCKED",
            "orders":[],"executable_candidates":[]}
