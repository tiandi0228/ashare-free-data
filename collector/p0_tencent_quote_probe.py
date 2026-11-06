"""Opt-in bounded Tencent A-share quote probe, for research only.

No live requests unless --live is explicitly provided. Does not modify
production collectors/checkpoints, certify price freshness, or issue trades.
Tencent's public text response is decoded, never evaluated as JavaScript.
"""
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SYMBOL = re.compile(r"^(?:sh6(?!88|89)[0-9]{5}|sz(?:000|001|002|003)[0-9]{3})$")
LINE = re.compile(r'v_(sh[0-9]{6}|sz[0-9]{6})="([^"\r\n]*)";?')
STAMP = re.compile(r"^20[0-9]{12}$")
MAX_SYMBOLS = 16
URL = "https://qt.gtimg.cn/q="
MAX_BYTES = 128 * 1024


def validate_symbols(symbols):
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= MAX_SYMBOLS:
        raise ValueError("only 1–16 research symbols allowed")
    if any(not isinstance(s, str) or not SYMBOL.fullmatch(s) for s in symbols):
        raise ValueError("SH/SZ main-board symbols required")
    if len(set(symbols)) != len(symbols):
        raise ValueError("duplicate symbols")
    return symbols


def decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        return None
    n = float(value)
    return n if n == n and n != float("inf") else None


def parse(raw, symbols):
    validate_symbols(symbols)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("invalid response bytes")
    text = raw.decode("gb18030", errors="strict")
    matches = list(LINE.finditer(text))
    observed = {}
    for match in matches:
        sym, fields_text = match.groups()
        if sym not in symbols:
            raise ValueError("unrequested symbol in batch response")
        if sym in observed:
            raise ValueError("duplicate symbol in response")
        fields = fields_text.split("~")
        if len(fields) <= 38 or fields[2] != sym[2:]:
            raise ValueError("quote schema or code mismatch")
        stamp = fields[30]
        if not STAMP.fullmatch(stamp):
            raise ValueError("invalid quote timestamp")
        try:
            datetime.strptime(stamp, "%Y%m%d%H%M%S")
        except ValueError as exc:
            raise ValueError("impossible quote timestamp") from exc
        price, previous = decimal(fields[3]), decimal(fields[4])
        if price is None or previous is None:
            state = "UNPRICED"
        elif price <= 0 or previous <= 0:
            state = "ZERO_PRICE_NEEDS_REVIEW"
        else:
            state = "NUMERIC_OBSERVED_UNVERIFIED"
        observed[sym] = {
            "symbol": sym, "quote_name": fields[1][:100],
            "price": price, "previous_close": previous,
            "provider_timestamp_cn": stamp,
            "state": state,
        }
    if not matches:
        raise ValueError("no parseable quote lines")
    return [observed.get(s, {"symbol": s, "state": "MISSING_QUOTE"}) for s in symbols]


def fetch(symbols, timeout_seconds=8):
    validate_symbols(symbols)
    if not 1 <= timeout_seconds <= 10:
        raise ValueError("timeout exceeds bounded research policy")
    request = Request(URL + ",".join(symbols), headers={
        "User-Agent": "StockMate-Research-Quote-Probe/1.0",
        "Accept": "text/plain,*/*",
    })
    with urlopen(request, timeout=timeout_seconds) as response:
        if response.status != 200:
            raise ValueError("provider HTTP error")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("provider response too large")
    return raw


def capture(symbols, out, transport=fetch, now=None):
    validate_symbols(symbols)
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    destination = Path(out)
    if destination.exists():
        raise ValueError("output destination must not exist: original receipt is immutable")
    destination.mkdir(parents=True)
    status = "FAILED_NO_TRADING"
    report = {
        "phase": "P0_TENCENT_BOUNDED_RESEARCH_PROBE",
        "source": "Tencent public quote text (unofficial)",
        "url_host": "qt.gtimg.cn",
        "requested_symbols": symbols,
        "observed_at_utc": timestamp,
        "official_exchange_timestamp_verified": False,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "paid_api_calls": 0,
    }
    try:
        raw = transport(symbols)
        # Archive the original bytes even if parsing fails.
        (destination / "quote_response.bin").write_bytes(raw)
        report["response_sha256"] = hashlib.sha256(raw).hexdigest()
        report["response_bytes"] = len(raw)
        rows = parse(raw, symbols)
        (destination / "quotes.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        report["states"] = {s: sum(q["state"] == s for q in rows)
                            for s in sorted({q["state"] for q in rows})}
        status = "OBSERVED_UNVERIFIED" if all(
            q["state"] == "NUMERIC_OBSERVED_UNVERIFIED" for q in rows
        ) else "PARTIAL_UNVERIFIED"
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        report["error_type"] = type(exc).__name__
        report["error_detail"] = str(exc)[:160]
    report["status"] = status
    (destination / "quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--live", action="store_true", help="Explicitly allow one bounded network request")
    args = ap.parse_args()
    symbols = validate_symbols(args.symbols)
    if not args.live:
        ap.error("network disabled by default; explicit --live required")
    result = capture(symbols, args.out)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "OBSERVED_UNVERIFIED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
