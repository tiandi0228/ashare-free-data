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

BATCH_START = date(2026, 9, 14)
RISK_WARNING_REVIEW = {"sh.600363", "sh.603517", "sh.603838"}
# Source notices and their provenance limits are documented in
# docs/p2-p3-remaining-14-gap-review.md. End dates are exclusive.
BATCH_CASES = {
    "sh.600363": (33, [["2026-09-29","2026-09-30"]],
                   "e4c01fa609951f30d25ec28ff729fa862c4815eca4ae279c9d7aeb1940f0fee2"),
    "sh.600825": (78, [["2026-09-08","2026-09-21"],["2026-10-13","2026-10-16"]],
                   "63ae1dd1502c2340aea79be6144a58d2256ed7edeb8c72b3bc69f289eb673e8a"),
    "sh.601238": (104, [["2026-09-14","2026-09-29"]],
                   "a2f6d4f36ec5487329a8e66a56bdf872c4dfc1e9a1cb2eb565994628800b7e65"),
    "sh.601995": (120, [["2026-09-15","2026-09-23"]],
                   "c62152568423890c5bfc384fa4e0ec34e9ef71b9a092011b75b83a9e282d6609"),
    "sh.603159": (137, [["2026-09-10","2026-09-17"]],
                   "c36cfc0437a88c63a3f63385a147c8f203cb0fc29ea5086dd71f32607bc24eb2"),
    "sh.603183": (140, [["2026-09-30","2026-10-09"]],
                   "3f53cf0bd447c2d757488614b4236632069885e793ee04959ae0c888c614168c"),
    "sh.603400": (161, [["2026-09-15","2026-09-30"]],
                   "d7d67226a1430bc3c0a56a4e48f08871f1a6dfb996043cc8f6d5c1523a6d60f5"),
    "sh.603517": (166, [["2026-10-19","2026-10-20"]],
                   "f6e5848ea8ff0e682608d96342adf68594140f9e7eac3aaad75afbfb2dc2394a"),
    "sh.603759": (182, [["2026-10-19","2026-10-20"]],
                   "b5d17da3ca737e21479b5e4b5a1ad41c7f13f777f42b8eaf419f30c35dcce4dc"),
    "sh.603838": (186, [["2026-10-19","2026-10-20"]],
                   "98441e8dcbfae442ec14a7004a95ce5abff8d876b8cd69e1e754a77b16436e86"),
    "sh.605303": (208, [["2026-09-14","2026-09-29"]],
                   "6c96135604c6cacdccc054c0babd022c3ac21488ab1c3597c7628f763b653688"),
    "sz.002813": (372, [["2026-09-30","2026-10-14"]],
                   "cb54189b8e76230ba70324a16fb53c6b316c0ce4c64dd3e2ff066177e82cf08f"),
    "sz.002860": (378, [["2026-09-22","2026-10-14"]],
                   "c1e9e5844abed70f2471cb337bf917f584f0029109aac7c0bfb80ae85ad1d188"),
    "sz.002870": (379, [["2026-09-01","2026-09-15"]],
                   "9f69a30a532df4e4178109d0c886f30c82e1f8fd1cf9e0fb3693f13582d3935a"),
}


def compare_notice_window(raw, issuer, windows, digest):
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("original CSV SHA mismatch")
    intervals = [(date.fromisoformat(start), date.fromisoformat(end))
                 for start, end in windows]
    if (not intervals or any(not start < end <= ASOF for start, end in intervals)
            or any(a[1] >= b[0] for a, b in zip(intervals, intervals[1:]))):
        raise ValueError("invalid notice intervals")
    observed = {}
    previous = None
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        day = date.fromisoformat(row["date"])
        if row["code"] != issuer or row["tradestatus"] not in ("0", "1"):
            raise ValueError("unexpected issuer or trading status")
        if (previous is not None and day <= previous) or day > ASOF:
            raise ValueError("duplicate, unsorted or post-as-of row")
        previous = day
        if BATCH_START <= day <= ASOF:
            observed[day] = row["tradestatus"]
    expected = {}
    for offset in range((ASOF - BATCH_START).days + 1):
        day = BATCH_START + timedelta(days=offset)
        if day.weekday() < 5 and day not in CLOSED:
            expected[day] = "0" if any(start <= day < end for start, end in intervals) else "1"
    if len(expected) != 21 or observed != expected:
        raise ValueError("session dates or statuses do not match")
    return {"issuer": issuer, "rows_matched": len(expected),
            "halt_rows_matched": sum(x == "0" for x in expected.values()),
            "risk_warning_review_required": issuer in RISK_WARNING_REVIEW}


def read_original(root, issuer, shard, digest):
    folder = Path(root) / EPOCH / f"shard_{shard:04d}"
    quality = json.loads((folder / "quality.json").read_text())
    entries = [x for x in quality["results"] if x["code"] == issuer]
    if (quality.get("trade_gate") != "BLOCKED" or len(entries) != 1
            or entries[0].get("sha256") != digest):
        raise ValueError("archived quality receipt does not match pinned original")
    return (folder / (issuer.replace(".", "_") + ".csv")).read_bytes()


def replay(root, batch=False):
    out = []
    if batch:
        for issuer, (shard, windows, digest) in BATCH_CASES.items():
            out.append(compare_notice_window(read_original(root, issuer, shard, digest),
                                             issuer, windows, digest))
    else:
        for issuer, (shard, start, resume, digest) in CASES.items():
            out.append(compare_rows(read_original(root, issuer, shard, digest),
                                    issuer, start, resume, digest))
    return {"cases": out, "asof": ASOF.isoformat(), "feature_gaps_closed": 0,
            "historical_PIT_verified": False, "trade_gate": "BLOCKED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--remaining-14", action="store_true")
    args = parser.parse_args()
    print(json.dumps(replay(args.archive_root, batch=args.remaining_14), indent=2))
