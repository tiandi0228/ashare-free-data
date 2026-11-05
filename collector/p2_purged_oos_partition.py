"""P2 chronology-only purged/embargoed OOS partition contract.

No performance estimation: this verifies only that explicitly dated research
events have separated feature, label, and future observation windows.
Historical PIT, survivorship control, universe membership and strategy
selection still need independent data evidence before any OOS trading claim.
"""
from datetime import date,timedelta

PHASE="P2_PURGED_EMBARGOED_TIME_SPLIT_OFFLINE_CONTRACT"
MAX=10000

def _day(s):
    if not isinstance(s,str):raise ValueError("date must be ISO")
    d=date.fromisoformat(s)
    if d.isoformat()!=s:raise ValueError("noncanonical date")
    return d

def partition(rows,train_end,validation_start,validation_end,embargo_days):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "historical_PIT_verified":False,"historical_OOS_validated":False,
          "returns_computed":False,"orders":[],"executable_candidates":[],
          "buy_recommendations_authorized":False}
    def fail(reason):return dict(base,reason=reason)
    try:
        t=_day(train_end);v=_day(validation_start);e=_day(validation_end)
        if (t>=v or v>e or type(embargo_days) is not int
            or not 0<=embargo_days<=30):
            return fail("INVALID_TIME_FOLDS")
        if not isinstance(rows,list) or not 1<=len(rows)<=MAX:
            return fail("INVALID_EVENT_INPUT")
        seen=set()
        train=[];holdout=[];excluded=[]
        for item in rows:
            if (not isinstance(item,dict) or not isinstance(item.get("id"),str)
                or not item["id"] or item["id"] in seen):
                return fail("DUPLICATED_OR_INVALID_EVENT_ID")
            seen.add(item["id"])
            if item.get("source") not in ("ARCHIVED_VENDOR_RESEARCH_UNVERIFIED",
                                          "SYNTHETIC_OFFLINE_FIXTURE"):
                return fail("UNTRUSTED_EVENT_PROVENANCE")
            feature=_day(item.get("feature_asof"))
            label_start=_day(item.get("label_start"))
            label_end=_day(item.get("label_end"))
            if label_start<feature or label_end<label_start:
                return fail("FUTURE_WINDOW_BEFORE_FEATURE")
            # Split is by available label information, not signal timestamp
            # alone. Any event crossing boundary is purged.
            if feature<=t and label_end<=t:
                train.append(item["id"])
            elif (feature>=v and feature<=e
                  and label_start>=v and label_end<=e):
                holdout.append(item["id"])
            else:
                excluded.append({"id":item["id"],
                                 "reason":"CROSSES_PURGED_OR_HOLDOUT_BOUNDARY"})
        # Calendar-day embargo is deliberately stronger than a zero-gap split.
        if (v-t).days<=embargo_days:
            return fail("EMBARGO_NOT_ENFORCED")
        if not train or not holdout:
            return fail("TRAIN_OR_HOLDOUT_EMPTY")
        if set(train)&set(holdout):
            return fail("FOLD_OVERLAP")
        return dict(base,status="TIME_WINDOWS_PURGED_NOT_HISTORICAL_OOS_CERTIFICATION",
                    train_end=t.isoformat(),
                    validation_start=v.isoformat(),
                    validation_end=e.isoformat(),
                    embargo_calendar_days=embargo_days,
                    training_event_ids=train,
                    holdout_event_ids=holdout,
                    excluded_events=excluded,
                    train_count=len(train),holdout_count=len(holdout),
                    purged_count=len(excluded),
                    data_label_availability_authenticated=False,
                    parameters_frozen_before_holdout_verified=False,
                    full_historical_universe_verified=False,
                    strategy_returns_or_win_rate_certified=False)
    except (TypeError,ValueError,KeyError,OverflowError):
        return fail("INVALID_EVENT_DATE_OR_FIELDS")

def contract_summary():
    return {"phase":PHASE,"train_holdout_partition_logic_available":True,
            "strategy_OOS_performance_verified":False,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
