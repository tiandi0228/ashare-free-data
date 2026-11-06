"""One-shot, non-trading Tencent sample observation; strict fixed request budget.

A single batched quote query for eight main-board symbols and five minute
periods for each of two symbols (11 HTTP requests total). Never retries,
schedules, places orders, or upgrades P1 certified shard counts.
"""
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from collector import p0_tencent_quote_probe as quote
from collector import p1_tencent_minute_probe as minute

QUOTE_SYMBOLS = (
    "sh600519", "sh600036", "sh601318", "sh601398",
    "sz000001", "sz000333", "sz002249", "sz002415",
)
MINUTE_SYMBOLS = ("sh600519", "sz002249")
PERIODS = ("m1", "m5", "m15", "m30", "m60")
MAX_REQUESTS = 11


def plan():
    assert len(QUOTE_SYMBOLS) == 8
    quote.validate_symbols(list(QUOTE_SYMBOLS))
    assert len(MINUTE_SYMBOLS) == 2 and all(x in QUOTE_SYMBOLS for x in MINUTE_SYMBOLS)
    assert PERIODS == minute.PERIODS
    return [("quote", tuple(QUOTE_SYMBOLS), None)] + [
        ("minute", symbol, period) for symbol in MINUTE_SYMBOLS for period in PERIODS
    ]


def collect(root, quote_transport=quote.fetch, minute_transport=minute.fetch,
            clock=time.monotonic):
    tasks = plan()
    if len(tasks) != MAX_REQUESTS:
        raise ValueError("changed live request budget")
    directory = Path(root)
    if directory.exists():
        raise ValueError("output destination already exists")
    directory.mkdir(parents=True)
    results = []
    for index, (kind, symbol, period) in enumerate(tasks):
        label = "quote_8" if kind == "quote" else f"{symbol}_{period}"
        dest = directory / f"{index:02d}_{label}"
        started = clock()
        if kind == "quote":
            report = quote.capture(list(symbol), dest, transport=quote_transport)
        else:
            report = minute.capture(symbol, period, dest, transport=minute_transport)
        elapsed = max(0.0, clock() - started)
        if (report.get("trade_gate") != "BLOCKED"
                or report.get("historical_PIT_verified") is not False
                or report.get("orders") != []
                or report.get("executable_candidates") != []):
            raise ValueError("unsafe vendor quality report")
        results.append({
            "request_number": index + 1,
            "request_type": kind,
            "symbol": list(symbol) if kind == "quote" else symbol,
            "period": period,
            "status": report.get("status"),
            "duration_ms": round(elapsed * 1000, 2),
            "original_sha256": report.get("response_sha256"),
            "response_bytes": report.get("response_bytes"),
            "rows": report.get("row_count"),
            "states": report.get("states"),
            "first_cn": report.get("first_timestamp_cn"),
            "last_cn": report.get("last_timestamp_cn"),
            "error_type": report.get("error_type"),
        })
    durations = sorted(x["duration_ms"] for x in results)
    # Nearest-rank P95: deterministic and meaningful for a small sample.
    p95 = durations[(95 * len(durations) + 99) // 100 - 1]
    quote_statuses = results[0].get("states") or {}
    ok = sum(x["status"] == "OBSERVED_UNVERIFIED" for x in results)
    summary = {
        "phase": "TENCENT_BOUNDED_EIGHT_QUOTE_TWO_SYMBOL_FIVE_PERIOD_PILOT",
        "status": "OBSERVED_UNVERIFIED" if ok == len(results) else "PARTIAL_OR_FAILED_UNVERIFIED",
        "requested_quote_symbols": list(QUOTE_SYMBOLS),
        "minute_symbols": list(MINUTE_SYMBOLS),
        "minute_periods": list(PERIODS),
        "request_count": len(results),
        "expected_request_count": MAX_REQUESTS,
        "successful_request_count": ok,
        "quote_numeric_observed_count": quote_statuses.get("NUMERIC_OBSERVED_UNVERIFIED", 0),
        "quote_requested_count": len(QUOTE_SYMBOLS),
        "latency_p50_ms": round(statistics.median(durations), 2),
        "latency_p95_nearest_rank_ms": p95,
        "results": results,
        "all_minute_periods_observed": all(
            x["status"] == "OBSERVED_UNVERIFIED" for x in results[1:]
        ),
        "full_market_bars_certified": False,
        "historical_PIT_verified": False,
        "official_exchange_timestamp_verified": False,
        "real_time_freshness_certified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }
    (directory / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    if not args.live:
        ap.error("network disabled; explicit --live required")
    summary = collect(args.out)
    print(json.dumps(summary, ensure_ascii=False))
    # Fail closed when any requested sample did not provide parseable rows;
    # workflow still uploads complete diagnostics.
    if summary["successful_request_count"] != MAX_REQUESTS:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
