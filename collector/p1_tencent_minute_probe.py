"""Bounded Tencent minute-K research capture. Never enables trades.

One symbol, one 1/5/15/30/60-minute period and up to 240 provider bars.
External transport disabled unless --live is given. Preserve vendor-native
volume without asserting lots/shares, time certification or full coverage.
"""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from collector.p0_tencent_quote_probe import SYMBOL

PERIODS = ("m1", "m5", "m15", "m30", "m60")
URL = "https://ifzq.gtimg.cn/appstock/app/kline/mkline?param="
LIMIT_BYTES = 512 * 1024


def request_url(symbol, period, limit=240):
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol):
        raise ValueError("沪深主板代码不合法")
    if period not in PERIODS:
        raise ValueError("unsupported minute period")
    if type(limit) is not int or not 1 <= limit <= 240:
        raise ValueError("sample count must be 1–240")
    return f"{URL}{symbol},{period},,{limit}"


def number(raw, name):
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        raise ValueError(f"invalid {name}")
    try:
        n = float(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {name}") from exc
    if not math.isfinite(n):
        raise ValueError(f"nonfinite {name}")
    return n


def parse(raw, symbol, period):
    request_url(symbol, period)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= LIMIT_BYTES:
        raise ValueError("invalid raw response size")
    try:
        p = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("not valid provider JSON") from exc
    if not isinstance(p, dict) or p.get("code") != 0:
        raise ValueError("unrecognized provider success schema")
    root = p.get("data")
    item = root.get(symbol) if isinstance(root, dict) else None
    rows = item.get(period) if isinstance(item, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= 240:
        raise ValueError("missing or excessive minute rows")
    result = []
    previous = None
    for row in rows:
        if not isinstance(row, list) or len(row) < 6 or not re.fullmatch(r"20\d{10}", str(row[0])):
            raise ValueError("bad minute K schema")
        stamp = str(row[0])
        try:
            t = datetime.strptime(stamp, "%Y%m%d%H%M")
        except ValueError as exc:
            raise ValueError("invalid minute date/time") from exc
        mins = t.hour * 60 + t.minute
        if not (570 <= mins <= 690 or 780 <= mins <= 900):
            raise ValueError("outside A-share trading session")
        if previous is not None and t <= previous:
            raise ValueError("duplicate or unordered minute bar")
        previous = t
        opened, closed, high, low, volume = [
            number(x, name) for x, name in zip(row[1:6], ("open", "close", "high", "low", "volume"))
        ]
        if (min(opened, closed, high, low) <= 0 or low > min(opened, closed)
                or high < max(opened, closed) or volume < 0):
            raise ValueError("invalid OHLC/volume")
        result.append({
            "timestamp_cn": stamp, "open": opened, "close": closed,
            "high": high, "low": low, "volume_provider_units": volume,
        })
    return result


def fetch(symbol, period, limit=240, timeout=8):
    url = request_url(symbol, period, limit)
    if not 1 <= timeout <= 10:
        raise ValueError("request timeout not bounded")
    req = Request(url, headers={"User-Agent": "StockMate-Research-Minute-Probe/1.0",
                                "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("provider HTTP failure")
        raw = response.read(LIMIT_BYTES+1)
    if len(raw) > LIMIT_BYTES:
        raise ValueError("oversized response")
    return raw


def capture(symbol, period, out, transport=fetch, now=None):
    url = request_url(symbol, period)
    dest = Path(out)
    if dest.exists():
        raise ValueError("output must not exist: preserve immutable raw evidence")
    dest.mkdir(parents=True)
    report = {
        "phase": "P1_TENCENT_MINUTE_RESEARCH_ONLY",
        "symbol": symbol, "period": period, "provider_url": url,
        "source": "Tencent public kline, unofficial",
        "observed_at_utc": (now or datetime.now(timezone.utc)).isoformat(),
        "status": "FAILED_UNVERIFIED",
        "bars_certified": False, "complete_one_minute_bar_verified": False,
        "point_in_time_universe_verified": False, "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "paid_api_calls": 0,
    }
    try:
        raw = transport(symbol, period)
        if not isinstance(raw, bytes) or len(raw) > LIMIT_BYTES:
            raise ValueError("unexpected response bytes")
        (dest/"response.bin").write_bytes(raw)
        report.update(response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw))
        rows = parse(raw, symbol, period)
        (dest/"bars.json").write_text(json.dumps(rows, indent=2)+"\n", encoding="utf-8")
        report.update(status="OBSERVED_UNVERIFIED", row_count=len(rows),
                      first_timestamp_cn=rows[0]["timestamp_cn"],
                      last_timestamp_cn=rows[-1]["timestamp_cn"])
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        report.update(error_type=type(exc).__name__, error_detail=str(exc)[:160])
    (dest/"quality.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--period", required=True, choices=PERIODS)
    ap.add_argument("--out", required=True)
    ap.add_argument("--live", action="store_true")
    args=ap.parse_args()
    request_url(args.symbol, args.period)
    if not args.live:
        ap.error("network disabled by default; explicitly pass --live")
    report=capture(args.symbol, args.period, args.out)
    print(json.dumps(report, ensure_ascii=False))
    if report["status"] != "OBSERVED_UNVERIFIED":
        raise SystemExit(2)


if __name__=="__main__":
    main()
