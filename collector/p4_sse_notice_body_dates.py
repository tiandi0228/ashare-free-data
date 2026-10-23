"""Inspect live SSE holiday notice body for every curated closure interval (research only)."""
import argparse,html,json,re,urllib.request
from pathlib import Path
from collector.p4_sse_holiday_crosscheck import OFFICIAL_SSE_NOTICES,HOLIDAY_RANGES

def inspect(year,raw):
    text=html.unescape(raw.decode("utf-8","replace"))
    text=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",text)
    text=re.sub(r"(?s)<[^>]*>"," ",text)
    text=re.sub(r"\s+","",text)
    misses=[];unpaired=[]
    for start,end in HOLIDAY_RANGES[year]:
        # A notice may state holidays in Chinese date notation; this is a conservative
        # presence-only check, never an exact semantic interpretation of opening days.
        def md(s):
            y,m,d=map(int,s.split("-"))
            return f"{m}月{d}日"
        if md(start) not in text or md(end) not in text:misses.append([start,end])
        else:
            left=md(start);right=md(end)
            # Must occur as a single local span, not scattered elsewhere on page.
            # Exchange notices insert weekday annotations between date and "至".
            # Keep spans bounded; require the closure term after the end date.
            middle=r"(?:[^。；;]{0,38}?)"
            right_expr=re.escape(right)
            if start[:7]==end[:7]:
                right_expr=r"(?:"+right_expr+r"|"+re.escape(str(int(end[-2:]))+"日") +r")"
            pair=re.search(re.escape(left)+middle+r"(?:至|到|—|－|–|~|～|[-])"+middle+right_expr+r"[^。；;]{0,80}休市",text)
            if start==end:
                pair=re.search(re.escape(left)+r"[^。；;]{0,45}休市",text)
            if pair is None:unpaired.append([start,end])
    return {"year":year,"ranges_expected":len(HOLIDAY_RANGES[year]),
            "ranges_missing_textual_dates":misses,
            "ranges_without_adjacent_closure_phrase":unpaired,
            "adjacent_phrase_check_passed":not misses and not unpaired,
            "body_text_nonempty":bool(text),"body_semantically_authenticated":False}
def capture():
    result=[]
    for year,url in sorted(OFFICIAL_SSE_NOTICES.items()):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=12) as r:
                final=r.geturl();raw=r.read(3_000_001)
                host=urllib.request.urlparse(final).hostname or ""
                if not (host=="sse.com.cn" or host.endswith(".sse.com.cn")) or len(raw)>3_000_000 or r.status!=200:
                    raise ValueError("untrusted or oversized response")
            item=inspect(year,raw);item["fetch_status"]="FETCHED"
        except (OSError,ValueError) as exc:
            item={"year":year,"fetch_status":"UNAVAILABLE","error_type":type(exc).__name__,
                  "ranges_missing_textual_dates":HOLIDAY_RANGES[year],"body_semantically_authenticated":False}
        result.append(item)
    return {"phase":"P4_SSE_NOTICE_BODY_DATE_PRESENCE","results":result,
            "body_dates_all_present":all(x["fetch_status"]=="FETCHED" and not x["ranges_missing_textual_dates"] for x in result),
            "historical_exchange_calendar_authenticated":False,"trade_gate":"BLOCKED","orders":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
    v=capture();out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(v,ensure_ascii=False))
if __name__=="__main__":main()
