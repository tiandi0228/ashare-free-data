"""Reconcile claimed next-day one-word limit-up against SHA-pinned minute CSV.

This is local-byte integrity verification, NOT external provider authentication.
Minute OHLC can refute a one-word shape if a nonzero-volume executed bar trades
below the alleged ceiling, but cannot certify opening auction or all exchange
trades even if every captured bar matches.
"""
import argparse
import csv
import hashlib
import io
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from collector.p4_oneword_prediction_replay import RULE, _date, _price, assess as daily_assess
from collector.p4_dual_horizon_research import MAINBOARD

PHASE = "P4_ONE_WORD_MINUTE_SOURCE_REPLAY_RESEARCH_ONLY"
SHA = re.compile(r"[a-f0-9]{64}\Z")
MAX_CSV_BYTES = 1_000_000
MAX_BARS = 300
COLUMNS = ["session_on", "time", "issuer", "open", "high", "low", "close", "volume"]


def replay(forecast, minute_data, source):
    if not isinstance(forecast, dict):
        raise ValueError("forecast required")
    # Reuse strict no-trade, date, issuer and rule contract.
    base = daily_assess(forecast)
    if forecast.get("observation") is not None:
        raise ValueError("do not mix self-reported daily OHLC with minute replay")
    issuer = base["issuer"]
    target = _date(base["session_on"])
    if not isinstance(source, dict):
        raise ValueError("minute source metadata required")
    if (not isinstance(source.get("source_ref"), str)
        or not source["source_ref"].startswith("https://")
        or len(source["source_ref"]) > 512
        or not isinstance(source.get("source_sha256"), str)
        or not SHA.fullmatch(source["source_sha256"])
        or type(source.get("claimed_full_trading_session")) is not bool
        or type(source.get("official_exchange_origin_authenticated")) is not bool):
        raise ValueError("incomplete source metadata")
    if not isinstance(minute_data, bytes) or not 0 < len(minute_data) <= MAX_CSV_BYTES:
        raise ValueError("bounded raw minute CSV required")
    digest = hashlib.sha256(minute_data).hexdigest()
    if digest != source["source_sha256"]:
        raise ValueError("raw minute CSV SHA mismatch")
    try:
        decoded = minute_data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("invalid minute CSV encoding") from None
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    if reader.fieldnames != COLUMNS:
        raise ValueError("unsupported minute CSV schema")
    bars = []
    previous_time = None
    for i, row in enumerate(reader):
        if i >= MAX_BARS:
            raise ValueError("unbounded minute CSV rows")
        if None in row or any(not isinstance(v, str) for v in row.values()):
            raise ValueError("CSV field count mismatch")
        if _date(row["session_on"]) != target or row["issuer"] != issuer:
            raise ValueError("cross-date or cross-issuer minute contamination")
        time = row["time"]
        if not isinstance(time, str) or not re.fullmatch(r"(?:09|10|11|13|14|15):[0-5][0-9]", time):
            raise ValueError("invalid intraday time")
        stamp = datetime.strptime(time, "%H:%M").time()
        # Accept ordinary exchange trading minutes only, not invented auction prints.
        # 09:30..11:30 and 13:00..15:00 inclusive; final-bar time labeling varies.
        if not (("09:30" <= time <= "11:30") or ("13:00" <= time <= "15:00")):
            raise ValueError("minute outside observed continuous session")
        if previous_time is not None and stamp <= previous_time:
            raise ValueError("duplicate or nonchronological minute")
        previous_time = stamp
        values = {k: _price(row[k]) for k in ("open", "high", "low", "close")}
        if not (values["low"] <= values["open"] <= values["high"]
                and values["low"] <= values["close"] <= values["high"]):
            raise ValueError("internally inconsistent minute OHLC")
        try:
            vol = Decimal(row["volume"])
        except Exception:
            raise ValueError("invalid minute trade volume") from None
        if not vol.is_finite() or vol < 0 or vol != vol.to_integral_value():
            raise ValueError("invalid minute trade volume")
        bars.append((time, values, vol))
    if not bars:
        raise ValueError("no minute price observations")
    if not any(vol > 0 for _, _, vol in bars):
        raise ValueError("minute bars contain no actual traded volume")
    ceiling = _price(source.get("claimed_limit_up_price"))
    prev_close = _price(source.get("claimed_previous_close"))
    if ceiling < prev_close:
        raise ValueError("claimed limit below previous close")
    if any(values["high"] > ceiling for _, values, vol in bars if vol > 0):
        raise ValueError("observed trade above claimed legal limit")
    offending = [time for time, values, vol in bars if vol > 0 and values["low"] < ceiling]
    state = ("CONTRADICTED_BY_LOCALLY_REPLAYED_MINUTE_LOW"
             if offending else "MINUTE_BARS_COMPATIBLE_ONE_WORD_NOT_CERTIFIED")
    # Even a full-looking 240 minute series doesn't establish auction or tick
    # completeness, provider identity, legal ceiling, or a fill.
    return {
        "phase": PHASE, "issuer": issuer,
        "predicted_on": base["predicted_on"],
        "session_on": target.isoformat(),
        "forecast_rule": RULE,
        "raw_csv_sha256_checked": True,
        "raw_csv_sha256": digest,
        "observed_minute_rows": len(bars),
        "observed_nonzero_volume_bars": sum(vol > 0 for _, _, vol in bars),
        "first_observed_minute": bars[0][0],
        "last_observed_minute": bars[-1][0],
        "claimed_complete_session_by_provider": source["claimed_full_trading_session"],
        "official_source_authenticated_by_this_replay": False,
        "original_tick_stream_independently_replayed": False,
        "opening_auction_independently_authenticated": False,
        "official_security_price_limit_authenticated": False,
        "audit_state": state,
        "first_contradictory_minute": offending[0] if offending else None,
        "one_word_limit_up_certified": False,
        "forecast_accuracy_claimed": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    result = replay(json.loads(a.forecast.read_text(encoding="utf-8")),
                    a.csv.read_bytes(),
                    json.loads(a.source.read_text(encoding="utf-8")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"phase": PHASE, "audit_state": result["audit_state"],
                      "trade_gate": "BLOCKED"}))


if __name__ == "__main__":
    main()
