"""Bounded free public-source history check; NEVER a trade signal."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

CODES = ("600000", "000001", "601398")
START, END = date(2024, 10, 20), date(2026, 10, 20)
MAX_ROWS = 600
MAX_BYTES = 1_000_000

def check_frame(df, code):
    if df is None or df.empty or len(df) > MAX_ROWS:
        raise ValueError("empty or oversized response")
    if not {"日期", "股票代码"}.issubset(df.columns):
        raise ValueError("missing identity/date columns")
    if set(str(s).zfill(6) for s in df["股票代码"]) != {code}:
        raise ValueError("issuer identity mismatch")
    dates = [date.fromisoformat(str(v)[:10]) for v in df["日期"]]
    if dates != sorted(set(dates)) or min(dates) < START or max(dates) > END:
        raise ValueError("duplicate, unsorted, or out-of-range dates")
    raw = df.to_csv(index=False).encode("utf-8-sig")
    if len(raw) > MAX_BYTES:
        raise ValueError("source CSV oversized")
    return raw, dates

def run(out: Path, provider=None):
    if provider is None:
        import akshare as provider
    out.mkdir(parents=True, exist_ok=True)
    observations = []
    for code in CODES:
        item = {"code": code, "status": "ERROR", "publisher_authenticated": False}
        try:
            frame = provider.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=START.strftime("%Y%m%d"),
                end_date=END.strftime("%Y%m%d"),
                adjust="", timeout=12)
            raw, dates = check_frame(frame, code)
            (out / f"{code}.csv").write_bytes(raw)
            item.update(status="OBSERVED_UNVERIFIED", rows=len(dates),
                        first=dates[0].isoformat(), last=dates[-1].isoformat(),
                        sha256=hashlib.sha256(raw).hexdigest())
        except Exception as exc:
            item["error_type"] = type(exc).__name__
        observations.append(item)
    report = {
        "phase": "FREE_PUBLIC_SOURCE_CAPACITY_ONLY",
        "source": "Eastmoney via AkShare", "symbols": observations,
        "count_expected": len(CODES), "logical_sdk_calls": len(CODES),
        "underlying_http_count_verified": False, "paid_api_calls": 0,
        "full_market_coverage_verified": False,
        "point_in_time_universe_verified": False,
        "formal_st_halt_delist_verified": False, "strategy_validated": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []}
    (out / "quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if all(x["status"] == "OBSERVED_UNVERIFIED" for x in observations) else 2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    raise SystemExit(run(Path(args.out)))

if __name__ == "__main__":
    main()
