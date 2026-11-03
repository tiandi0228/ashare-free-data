"""Conservative research-only quote-versus-minute-close diagnostic.

A Tencent tick/last-price quote and Eastmoney minute bar are distinct
sampling semantics: even a numerically equal price CANNOT certify an
independent simultaneous executable quote. Reject stale/mismatched periods
and always maintain BLOCKED until independent time-aligned quotes exist.
"""
import datetime as dt
import decimal
from zoneinfo import ZoneInfo

D=decimal.Decimal
TZ=ZoneInfo("Asia/Shanghai")
def evaluate(quote, minute, checked_at):
    base={"phase":"P1_CROSS_SOURCE_RESEARCH_DIAGNOSTIC",
          "source_a":"tencent_unofficial_last_price",
          "source_b":"eastmoney_unofficial_completed_minute_close",
          "comparison_semantics":"NON_SIMULTANEOUS_QUOTE_VS_MINUTE_CLOSE",
          "cross_source_price_verified":False,
          "executable_quote":False,
          "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    def outcome(state,reason,**kwargs):
        return dict(base,status=state,reason=reason,**kwargs)
    try:
        if not isinstance(quote,dict) or not isinstance(minute,dict):
            raise ValueError("missing sources")
        t=dt.datetime.fromisoformat(checked_at)
        q=dt.datetime.fromisoformat(quote["quote_time"])
        b=dt.datetime.fromisoformat(minute["last_completed_minute_time"])
        if any(x.tzinfo is None or x.utcoffset() is None for x in (t,q,b)):
            raise ValueError("naive timestamp")
        t,q,b=(x.astimezone(TZ) for x in (t,q,b))
        if t.date()!=q.date() or q.date()!=b.date():
            return outcome("NOT_COMPARABLE","DIFFERENT_TRADING_DAYS")
        age=(t-q).total_seconds()
        if not -5<=age<=15:
            return outcome("NOT_COMPARABLE","QUOTE_STALE_OR_FUTURE",quote_age_seconds=round(age,2))
        if b>=t.replace(second=0,microsecond=0):
            return outcome("NOT_COMPARABLE","MINUTE_BAR_NOT_COMPLETED")
        if not 0<=(q-b).total_seconds()<=120:
            return outcome("NOT_COMPARABLE","MINUTE_QUOTE_TIME_TOO_FAR_APART")
        if minute.get("minute_validation_issues"):
            return outcome("NOT_COMPARABLE","MINUTE_VALIDATION_ISSUES_PRESENT")
        a=D(str(quote["price"]))
        c=D(str(minute["last_completed_minute_close"]))
        if not a.is_finite() or not c.is_finite() or a<=0 or c<=0:
            raise ValueError("invalid prices")
        delta=abs(a-c)
        relative=delta/c
        return outcome("RESEARCH_PRICE_PROXIMITY_ONLY",
                       "DIFFERENT_SAMPLING_SEMANTICS_NO_EXECUTION_CERTIFICATION",
                       quote_age_seconds=round(age,2),
                       minute_label=b.isoformat(),
                       quote_time=q.isoformat(),
                       absolute_difference_cny=str(delta),
                       relative_difference_pct=str((relative*100).quantize(
                           D("0.0001"),rounding=decimal.ROUND_HALF_UP)),
                       observed_within_one_tick=delta<=D("0.01"))
    except (KeyError,TypeError,ValueError,decimal.InvalidOperation,OverflowError):
        return outcome("NOT_COMPARABLE","SOURCE_EVIDENCE_INVALID")
