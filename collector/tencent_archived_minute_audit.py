"""Read-only replay of archived Tencent sample evidence, not market certification.

Rehash original bytes, reparse every original response, compare stored rows,
and describe within-session minute gaps. No provider calls, no bar imputation,
no cross-provider assertion, no trade execution.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from collector import p0_tencent_quote_probe as quote
from collector import p1_tencent_minute_probe as minute
from collector.tencent_eight_sample_pilot import QUOTE_SYMBOLS, MINUTE_SYMBOLS, PERIODS, MAX_REQUESTS

def _minutes(value):
    return datetime.strptime(value, "%Y%m%d%H%M")

def _session(t):
    n=t.hour*60+t.minute
    if 570<=n<=690:return "AM"
    if 780<=n<=900:return "PM"
    raise ValueError("minute outside trading session")

def _gaps(rows, period):
    width=int(period[1:])
    gaps=[]
    for a,b in zip(rows, rows[1:]):
        x,y=_minutes(a["timestamp_cn"]),_minutes(b["timestamp_cn"])
        if x.date()!=y.date() or _session(x)!=_session(y):
            continue
        delta=int((y-x).total_seconds()/60)
        if delta>width:
            gaps.append({"after_cn":a["timestamp_cn"],"before_cn":b["timestamp_cn"],
                         "gap_minutes":delta-width,"reason":"UNEXPLAINED_WITHIN_SESSION_GAP"})
        elif delta<width:
            gaps.append({"after_cn":a["timestamp_cn"],"before_cn":b["timestamp_cn"],
                         "gap_minutes":delta-width,"reason":"PERIOD_ALIGNMENT_OR_DUPLICATE"})
    return gaps

def replay(root):
    root=Path(root)
    report=json.loads((root/"summary.json").read_text(encoding="utf-8"))
    if (report.get("phase")!="TENCENT_BOUNDED_EIGHT_QUOTE_TWO_SYMBOL_FIVE_PERIOD_PILOT"
            or report.get("trade_gate")!="BLOCKED"
            or report.get("historical_PIT_verified") is not False
            or report.get("orders")!=[] or report.get("executable_candidates")!=[]
            or report.get("request_count")!=MAX_REQUESTS or len(report.get("results",[]))!=MAX_REQUESTS):
        raise ValueError("invalid or unsafe sample summary")
    checks=[]
    for i,item in enumerate(report["results"]):
        if type(item.get("request_number")) is not int or item["request_number"]!=i+1:
            raise ValueError("sample index mismatch")
        if i==0:
            if item.get("request_type")!="quote" or item.get("symbol")!=list(QUOTE_SYMBOLS) or item.get("period") is not None:
                raise ValueError("quote sample identity mismatch")
            folder=root/"00_quote_8"
            raw=(folder/"quote_response.bin").read_bytes()
            parsed=quote.parse(raw,list(QUOTE_SYMBOLS))
            stored=json.loads((folder/"quotes.json").read_text())
            if parsed!=stored:raise ValueError("quote rows not equal to replayed source")
            count=len(parsed)
            assessment={"kind":"quote","symbol_count":count,"provider_timestamps_cn":sorted({r.get("provider_timestamp_cn") for r in parsed if r.get("provider_timestamp_cn")})}
        else:
            sym=MINUTE_SYMBOLS[(i-1)//len(PERIODS)]
            period=PERIODS[(i-1)%len(PERIODS)]
            if item.get("request_type")!="minute" or item.get("symbol")!=sym or item.get("period")!=period:
                raise ValueError("minute sample identity mismatch")
            folder=root/f"{i:02d}_{sym}_{period}"
            raw=(folder/"response.bin").read_bytes()
            parsed=minute.parse(raw,sym,period)
            stored=json.loads((folder/"bars.json").read_text())
            if parsed!=stored:raise ValueError("minute rows not equal to replayed source")
            count=len(parsed)
            assessment={
                "kind":"minute","symbol":sym,"period":period,"observed_rows":count,
                "observed_days":len({r["timestamp_cn"][:8] for r in parsed}),
                "first_cn":parsed[0]["timestamp_cn"],"last_cn":parsed[-1]["timestamp_cn"],
                "within_session_gaps":_gaps(parsed,period),
                "gap_count":len(_gaps(parsed,period)),
                "volume_units":"PROVIDER_NATIVE_UNVERIFIED",
            }
        quality=json.loads((folder/"quality.json").read_text())
        if quality.get("trade_gate")!="BLOCKED" or quality.get("historical_PIT_verified") is not False:
            raise ValueError("unsafe source report")
        digest=hashlib.sha256(raw).hexdigest()
        if (item.get("original_sha256")!=digest or quality.get("response_sha256")!=digest
                or item.get("response_bytes")!=len(raw)
                or quality.get("response_bytes")!=len(raw)
                or item.get("status")!=quality.get("status")
                or quality.get("status")!="OBSERVED_UNVERIFIED"):
            raise ValueError("source byte hash/identity/status mismatch")
        if i and (item.get("rows")!=count or quality.get("row_count")!=count):
            raise ValueError("minute record count inconsistent")
        checks.append(assessment)
    return {
        "phase":"TENCENT_ARCHIVED_BYTE_REPLAY_CONTINUITY_AUDIT",
        "status":"RAW_REPLAY_MATCH_UNVERIFIED" if all(x.get("gap_count",0)==0 for x in checks)
                else "RAW_REPLAY_MATCH_WITH_UNEXPLAINED_GAPS",
        "source_requests_replayed":MAX_REQUESTS,
        "source_sha256_reverified":True,
        "period_gap_count":sum(x.get("gap_count",0) for x in checks),
        "checks":checks,
        "minute_volume_unit_certified":False,
        "minute_bar_completion_certified":False,
        "independent_vendor_confirmed":False,
        "full_market_bars_certified":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive-root",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    result=replay(args.archive_root)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":result["phase"],"status":result["status"],
                      "source_requests_replayed":result["source_requests_replayed"],
                      "period_gap_count":result["period_gap_count"],
                      "minute_checks":[{k:c[k] for k in ("symbol","period","observed_rows","gap_count")}
                                       for c in result["checks"] if c["kind"]=="minute"],
                      "trade_gate":result["trade_gate"]},ensure_ascii=False))

if __name__=="__main__":
    main()
