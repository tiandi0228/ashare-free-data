"""Retain raw status responses and distinguish observed status from first release."""
import argparse
import base64
from datetime import datetime, time
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
MAX_RAW = 1024 * 1024


def instant(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError("timestamp needs timezone")
    return stamp


def receipt(*, raw, issuer, source_url, source_time, captured_at, status, mapping):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RAW:
        raise ValueError("raw response size invalid")
    if not re.fullmatch(r"(sh|sz)\.\d{6}", issuer):
        raise ValueError("invalid issuer")
    url = urlsplit(source_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("provide canonical HTTPS source URL without credentials or query")
    if status not in ("HALTED", "TRADING", "UNKNOWN") or not mapping.strip():
        raise ValueError("invalid normalized status or missing mapping")
    observed = instant(captured_at).astimezone(SHANGHAI)
    source = instant(source_time).astimezone(SHANGHAI) if source_time else None
    if source and source > observed:
        raise ValueError("source timestamp is after capture")
    if source is None:
        timing = "NO_SOURCE_CLOCK"
    elif source.date() != observed.date():
        timing = "SOURCE_NOT_CAPTURE_DAY"
    elif observed.time() >= time(9, 15):
        timing = "NOT_CAPTURED_BEFORE_0915"
    else:
        timing = "SAME_DAY_CAPTURE_BEFORE_0915"
    return dict(schema="p3_preauction_receipt_v1", issuer=issuer, source_url=source_url,
                source_time=source.isoformat() if source else None, captured_at=observed.isoformat(),
                normalized_status_claim=status, field_mapping=mapping, timing=timing,
                capture_clock_attested=False, source_mapping_verified=False,
                historical_PIT_verified=False, official_first_release=None,
                preauction_visibility_certified=False, trade_gate="BLOCKED", orders=[],
                executable_candidates=[], raw_sha256=hashlib.sha256(raw).hexdigest(),
                raw_base64=base64.b64encode(raw).decode("ascii"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("raw", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("issuer", "source-url", "captured-at", "status", "mapping"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--source-time")
    args = parser.parse_args()
    with args.raw.open("rb") as source:
        raw = source.read(MAX_RAW + 1)
    result = receipt(raw=raw, issuer=args.issuer, source_url=args.source_url,
                     source_time=args.source_time, captured_at=args.captured_at,
                     status=args.status, mapping=args.mapping)
    with args.out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
