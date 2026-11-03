"""Free, bounded, read-only Tencent/Eastmoney A-share research snapshot. NO TRADES."""
import argparse,datetime as dt,json,math,re,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from collector.intraday_minute_coverage import audit_minute_coverage

TZ=ZoneInfo("Asia/Shanghai")
WATCHLIST=("002249","002696","301015","300015","300896")
CODE=re.compile(r"^(?:00|30|60|68)\d{4}$")
class SourceFailure(ValueError):
    """Sanitized failure stage without exposing provider response or tokens."""
    def __init__(self,stage,cause):
        self.stage=stage
        self.error_type=type(cause).__name__
        super().__init__(stage+" failed")


def parse_tencent(raw,code):
    ticker=("sh" if code.startswith("6") else "sz")+code
    m=re.fullmatch(r'v_'+ticker+r'="([^"\r\n]+)";?\s*',raw.strip())
    if not m: raise ValueError("Tencent symbol mismatch")
    p=m.group(1).split("~")
    if len(p)<=49 or p[2]!=code or not re.fullmatch(r"\d{14}",p[30]):
        raise ValueError("Tencent field schema invalid")
    try: price,previous,volume,ratio=float(p[3]),float(p[4]),int(p[6]),float(p[49])
    except (ValueError,TypeError) as e: raise ValueError("Missing Tencent numeric field") from e
    if not all(math.isfinite(x) and x>0 for x in (price,previous,ratio)) or volume<0:
        raise ValueError("Invalid Tencent numeric field")
    stamp=dt.datetime.strptime(p[30],"%Y%m%d%H%M%S").replace(tzinfo=TZ)
    return dict(source="tencent_unofficial",code=code,name=p[1],price=price,
                prev_close=previous,volume_lots=volume,volume_ratio=ratio,
                quote_time=stamp.isoformat())

def parse_eastmoney(raw,code,now):
    data=json.loads(raw)
    obj=data.get("data")
    if data.get("rc")!=0 or not isinstance(obj,dict) or obj.get("code")!=code:
        raise ValueError("Eastmoney response invalid")
    lines=obj.get("trends")
    if not isinstance(lines,list) or not 1<=len(lines)<=260:
        raise ValueError("Eastmoney minute data missing or oversized")
    items=[];seen=set()
    for line in lines:
        parts=line.split(",")
        if len(parts)<7: raise ValueError("Invalid Eastmoney minute schema")
        try:
            ts=dt.datetime.strptime(parts[0],"%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            o,c,h,l,v,amt=(float(parts[i]) for i in range(1,7))
        except (ValueError,TypeError) as e: raise ValueError("Invalid minute value") from e
        if ts.date()!=now.date() or ts in seen or (items and ts<=items[-1][0]):
            raise ValueError("Old, duplicate or unordered minute")
        if (not all(math.isfinite(x) for x in (o,c,h,l,v,amt))
                or min(o,c,h,l)<=0 or l>min(o,c,h) or h<max(o,c,l)
                or v<0 or amt<0): raise ValueError("Invalid minute OHLC/volume")
        seen.add(ts);items.append((ts,v,amt))
    # Session-aware gaps: 11:30 -> 13:00/13:01 is a lunch break, not a gap.
    # We do not infer the full 241-minute source coverage from a short sample.
    session_issues=[]
    gaps=[]
    for ts,_,_ in items:
        if not (dt.time(9,30)<=ts.time()<=dt.time(11,30)
                or dt.time(13)<=ts.time()<=dt.time(15)):
            session_issues.append("OUTSIDE_CN_A_SHARE_SESSION")
    for (left,_,_),(right,_,_) in zip(items,items[1:]):
        if left.time()<=dt.time(11,30)<right.time():
            continue
        delta=int((right-left).total_seconds()/60)
        if delta!=1:
            gaps.append(dict(after=left.isoformat(),before=right.isoformat(),
                             minutes_missing=max(0,delta-1)))
    completed=[x for x in items if x[0]<now.replace(second=0,microsecond=0)]
    coverage=audit_minute_coverage([x[0] for x in items],now)
    # A-share vendor volume is in lots (100 shares). Reconcile against turnover
    # to catch silent unit drift without treating it as a regulatory proof.
    unit_mismatch=False
    for line,(ts,volume,amount) in zip(lines,items):
        fields=line.split(",")
        low,high=float(fields[4]),float(fields[3])
        if volume>0 and not (low*volume*100*0.95<=amount<=high*volume*100*1.05):
            unit_mismatch=True
    issues=list(dict.fromkeys(session_issues))
    if gaps: issues.append("OBSERVED_MINUTE_GAPS")
    if unit_mismatch: issues.append("VOLUME_AMOUNT_UNIT_MISMATCH")
    if coverage["source_has_future_labels"]:
        issues.append("OBSERVED_FUTURE_MINUTE_LABEL")
    if coverage["missing_expected_completed_labels"]:
        issues.append("EXPECTED_COMPLETED_MINUTES_MISSING")
    return dict(source="eastmoney_unofficial",rows_today=len(items),
                completed_minutes=len(completed),
                last_minute_time=items[-1][0].isoformat(),
                last_completed_minute_time=completed[-1][0].isoformat() if completed else None,
                completed_minute_volume_lots=sum(x[1] for x in completed),
                completed_minute_amount_cny=round(sum(x[2] for x in completed),2),
                minute_unit="lots_100_shares",observed_gaps=gaps,
                expected_minute_coverage=coverage,
                minute_validation_issues=issues,
                minute_data_complete=False)

def quality(q,m,now):
    age=(now-dt.datetime.fromisoformat(q["quote_time"])).total_seconds()
    reasons=[]
    if not(now.weekday()<5 and (dt.time(9,30)<=now.time()<=dt.time(11,30)
                            or dt.time(13)<=now.time()<=dt.time(15))):
        reasons.append("OUTSIDE_CONTINUOUS_TRADING")
    if dt.datetime.fromisoformat(q["quote_time"]).date()!=now.date():
        reasons.append("OLD_TRADING_DAY")
    if not -5<=age<=15: reasons.append("QUOTE_STALE_OR_FUTURE")
    if not m["completed_minutes"]: reasons.append("NO_COMPLETED_MINUTE")
    reasons.extend(m.get("minute_validation_issues",[]))
    if not m["minute_data_complete"]: reasons.append("MINUTE_COMPLETENESS_UNVERIFIED")
    return dict(status="RESEARCH_ONLY",quote_age_seconds=round(age,2),
                validation_issues=reasons,cross_source_price_verified=False,
                executable_quote=False,trade_gate="BLOCKED",orders=[],
                executable_candidates=[])

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req,timeout=12) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            # Never retry permanent HTTP errors such as 403 or 404.
            if attempt or exc.code not in (429,500,502,503,504):
                raise
        except (urllib.error.URLError,TimeoutError,ConnectionError,OSError):
            if attempt:
                raise
    raise RuntimeError("unreachable retry state")

def observe(code,now):
    if not CODE.fullmatch(code): raise ValueError("Bad symbol")
    ticker=("sh" if code.startswith("6") else "sz")+code
    params=dict(secid=("1." if code.startswith("6") else "0.")+code,
                ndays="1",iscr="0",
                fields1="f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                fields2="f51,f52,f53,f54,f55,f56,f57,f58")
    try:
        q=parse_tencent(fetch("https://qt.gtimg.cn/q="+ticker).decode("gbk"),code)
    except (OSError,UnicodeError,ValueError,TimeoutError) as exc:
        raise SourceFailure("TENCENT_QUOTE",exc) from exc
    url="https://push2.eastmoney.com/api/qt/stock/trends2/get?"+urllib.parse.urlencode(params)
    try:
        m=parse_eastmoney(fetch(url).decode("utf-8"),code,now)
    except (OSError,UnicodeError,ValueError,TimeoutError) as exc:
        raise SourceFailure("EASTMONEY_MINUTES",exc) from exc
    checked_at=dt.datetime.now(TZ)
    return dict(quote=q,minute=m,checked_at=checked_at.isoformat(),
                validation=quality(q,m,checked_at))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    p.add_argument("--codes",nargs="*",default=list(WATCHLIST))
    a=p.parse_args()
    if not 1<=len(a.codes)<=5 or len(set(a.codes))!=len(a.codes) or any(not CODE.fullmatch(c) for c in a.codes):
        p.error("Specify 1 to 5 unique A-share symbols")
    now=dt.datetime.now(TZ)
    result=dict(phase="P1_PUBLIC_INTRADAY_RESEARCH_SNAPSHOT",asof=now.isoformat(),
                provider_type="UNOFFICIAL_WEB_ENDPOINTS",trade_gate="BLOCKED",
                orders=[],executable_candidates=[],symbols={})
    for code in a.codes:
        try: result["symbols"][code]=observe(code,now)
        except SourceFailure as e:
            result["symbols"][code]=dict(status="SOURCE_UNAVAILABLE",error_stage=e.stage,
                                         error_type=e.error_type,
                                         executable_quote=False,trade_gate="BLOCKED",
                                         orders=[],executable_candidates=[])
        except (OSError,UnicodeError,ValueError,KeyError,TimeoutError) as e:
            result["symbols"][code]=dict(status="SOURCE_UNAVAILABLE",error_stage="UNKNOWN",
                                         error_type=type(e).__name__,
                                         executable_quote=False,trade_gate="BLOCKED",
                                         orders=[],executable_candidates=[])
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":result["phase"],"asof":result["asof"],
                       "status":{k:v.get("status",v.get("validation",{}).get("status"))
                                 for k,v in result["symbols"].items()},
                       "trade_gate":"BLOCKED"},ensure_ascii=False))

if __name__=="__main__": main()
