"""Screen a 600825 historical CSV export without authenticating its provenance."""
import argparse
import csv
from datetime import datetime, time
import hashlib
import json
from pathlib import Path
import re

from collector.p3_600825_sse_snapshot_preflight import BEIJING, TARGET, assess as no_snapshot

FORMATS = {
    "l1-snapshot": ("PhaseCode",),
    "l2-snapshot": ("TradingPhaseCode",),
    "l2-stock-tick": ("Type", "TickBSFlag"),
}
CUTOFF = datetime.strptime(TARGET, "%Y%m%d").replace(hour=9, minute=15, tzinfo=BEIJING)


def sending_time(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[0-9]{14}", raw):
        return None
    try:
        stamp = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=BEIJING)
    except ValueError:
        return None
    return stamp if raw[:8] == TARGET and stamp.time() != time(0) else None


def is_halt(row, kind):
    if kind == "l2-stock-tick":
        return row["Type"] == "S" and row["TickBSFlag"] == "SUSP"
    phase = row[FORMATS[kind][0]]
    # In the documented stock phase field, P in the first position is explicit.
    # A conflicting tradable/non-listed flag is not a usable candidate.
    return re.fullmatch(r"P[0 ][1 ][01 ] {4}", phase) is not None


def assess(stream, kind, *, digest=None):
    if kind not in FORMATS:
        raise ValueError("unsupported history format")
    base = no_snapshot()
    for key in ("exchange_sending_time_beijing", "last_update_time_beijing"):
        del base[key]
    counts = dict(security_rows=0, explicit_halt_rows=0, pre_auction_candidates=0,
                  halt_at_or_after_auction=0, halt_send_clock_unusable=0)
    result = {**base, **counts, "input_format": kind, "earliest_candidate_send_time_beijing": None,
              "status": "NO_HISTORICAL_CSV_SUPPLIED", "input_sha256": None,
              "earliest_candidate": None}
    if stream is None:
        return result
    reader = csv.DictReader(stream, strict=True)
    headers = reader.fieldnames or []
    required = {"SecurityID", "SendingTime", *FORMATS[kind]}
    if not required.issubset(headers) or len(set(headers)) != len(headers):
        raise ValueError("historical CSV headers missing or ambiguous")
    earliest = None
    candidate = None
    for row in reader:
        if row["SecurityID"] != "600825":
            continue
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"malformed target security row at line {reader.line_num}")
        counts["security_rows"] += 1
        if not is_halt(row, kind):
            continue
        counts["explicit_halt_rows"] += 1
        stamp = sending_time(row["SendingTime"])
        if stamp is None:
            counts["halt_send_clock_unusable"] += 1
        elif stamp >= CUTOFF:
            counts["halt_at_or_after_auction"] += 1
        else:
            counts["pre_auction_candidates"] += 1
            if earliest is None or stamp < earliest:
                earliest = stamp
                candidate = {
                    "csv_record_end_line": reader.line_num,
                    "sending_time_raw": row["SendingTime"],
                    **{key: row[key] for key in (*FORMATS[kind], "TickIndex", "ChannelNo", "TickTime",
                                                "DateTime") if key in row},
                }
    status = ("PRE_AUCTION_HALT_CANDIDATE_PROVENANCE_REQUIRED" if earliest
              else "NO_PRE_AUCTION_HALT_CANDIDATE_IN_SUPPLIED_CSV")
    return {**result, **counts, "status": status,
            "input_sha256": digest.hexdigest() if digest is not None else None,
            "earliest_candidate": candidate,
            "earliest_candidate_send_time_beijing": earliest.isoformat() if earliest else None}


def assess_file(path, kind, *, expected_sha256=None):
    if expected_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise ValueError("expected a lowercase SHA-256 digest")
    digest = hashlib.sha256()
    with path.open("rb") as raw:
        def decoded_lines():
            for number, line in enumerate(raw):
                digest.update(line)
                yield line.decode("utf-8-sig" if number == 0 else "utf-8")
        result = assess(decoded_lines(), kind, digest=digest)
    if expected_sha256 is not None and result["input_sha256"] != expected_sha256:
        raise ValueError("CSV SHA-256 mismatch")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=tuple(FORMATS), default="l2-stock-tick")
    parser.add_argument("--csv", type=Path, help="Historical CSV export with original column names")
    parser.add_argument("--sha256", help="Optional independently supplied file digest")
    args = parser.parse_args()
    if args.sha256 is not None and args.csv is None:
        parser.error("--sha256 requires --csv")
    if args.csv:
        result = assess_file(args.csv, args.format, expected_sha256=args.sha256)
    else:
        result = assess(None, args.format)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
