"""Bounded reproducible review of three P2 source gaps. Research only."""
import argparse
import csv
import hashlib
import io
import json
from datetime import date, timedelta
from pathlib import Path

ASOF = date(2026, 10, 20)
EPOCH = "5ba00fbd720fad90"
CLOSED = {date(2026, 9, 25), *(date(2026, 10, d) for d in range(1, 8))}
CASES = {
    "sh.601091": (97, "2026-09-17", None,
                  "a99a8383f8a3a41682a7264cac5a1a3097831bb2e456c2c36d09c188b8fcdf3d"),
    "sh.600293": (27, "2026-09-29", "2026-10-20",
                  "f18062e301843b403e52aa4ca7dbac511579a6f9683da74b414451a8ab38d56c"),
    "sh.600301": (27, "2026-09-14", "2026-09-21",
                  "2f163fecfb61ea758ecdbd98edb1d7a4b05c32172a78df31801ec3b9f3d5a5f4"),
}


def compare_rows(raw, issuer, start, resume, digest):
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("original CSV SHA mismatch")
    begin = date.fromisoformat(start)
    end = date.fromisoformat(resume) if resume else ASOF
    if not begin <= end <= ASOF:
        raise ValueError("review window outside as-of")
    observed = {}
    previous = None
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        day = date.fromisoformat(row["date"])
        if row["code"] != issuer or row["tradestatus"] not in ("0", "1"):
            raise ValueError("unexpected issuer or trading status")
        if (previous is not None and day <= previous) or day > ASOF:
            raise ValueError("duplicate, unsorted or post-as-of row")
        if resume is None and day < begin:
            raise ValueError("pre-listing row")
        previous = day
        if begin <= day <= end:
            observed[day] = row["tradestatus"]
    expected = {}
    for offset in range((end - begin).days + 1):
        day = begin + timedelta(days=offset)
        if day.weekday() < 5 and day not in CLOSED:
            expected[day] = "1" if resume is None or day == end else "0"
    if not expected or observed != expected:
        raise ValueError("session dates or statuses do not match")
    return {"issuer": issuer, "rows_matched": len(expected),
            "halt_rows_matched": sum(s == "0" for s in expected.values())}


def replay(root):
    out = []
    for issuer, (shard, start, resume, digest) in CASES.items():
        folder = Path(root) / EPOCH / f"shard_{shard:04d}"
        quality = json.loads((folder / "quality.json").read_text())
        entries = [x for x in quality["results"] if x["code"] == issuer]
        if (quality.get("trade_gate") != "BLOCKED" or len(entries) != 1
                or entries[0].get("sha256") != digest):
            raise ValueError("archived quality receipt does not match pinned original")
        raw = (folder / (issuer.replace(".", "_") + ".csv")).read_bytes()
        out.append(compare_rows(raw, issuer, start, resume, digest))
    return {"cases": out, "asof": ASOF.isoformat(), "feature_gaps_closed": 0,
            "historical_PIT_verified": False, "trade_gate": "BLOCKED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, required=True)
    print(json.dumps(replay(parser.parse_args().archive_root), indent=2))
