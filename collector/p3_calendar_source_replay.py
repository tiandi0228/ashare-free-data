"""Offline scoped daily calendar evidence from a pinned exchange notice."""
import argparse
import hashlib
import json
import re
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path

SOURCE = "https://www.szse.cn/www/disclosure/notice/general/t20260917_622911.html"
SHA = "7b0c4264d27f4ba14a1904ab31cb3b2b870e4e68d6b8d8c0f6cf4254c1a045a4"
FILE = Path("evidence/p3_calendar_sources/szse-20260917.html")
PUBLISHED = date(2026, 9, 17)
FIRST, LAST = date(2026, 9, 24), date(2026, 10, 12)


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = None

    def handle_starttag(self, tag, attrs):
        if tag in {"style", "script"}:
            self.skip = tag

    def handle_endtag(self, tag):
        if self.skip == tag:
            self.skip = None

    def handle_data(self, data):
        if self.skip is None:
            self.parts.append(data)


def day(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("expected canonical ISO day")
    return parsed


def notice(raw):
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError("official notice byte hash mismatch")
    parser = Text()
    parser.feed(raw.decode("utf-8"))
    parser.close()
    content = re.sub(r"\s+", "", "".join(parser.parts))
    if ("时间：2026-09-17" not in content or "深圳证券交易所2026年9月17日" not in content):
        raise ValueError("publisher or displayed publication day mismatch")
    body = re.search(r"一、休市安排(.*?)二、清算交收", content)
    if body is None:
        raise ValueError("closure section absent")
    pairs = re.findall(
        r"(\d+)月(\d+)日（星期.）至(\d+)月(\d+)日（星期.）休市，"
        r"(\d+)月(\d+)日（星期.）起照常开市", body[1],
    )
    if len(pairs) != 2:
        raise ValueError("unexpected closure intervals")
    closed, reopen = set(), set()
    for m1, d1, m2, d2, m3, d3 in pairs:
        first, last, opening = (date(2026, int(m), int(d))
                                for m, d in ((m1, d1), (m2, d2), (m3, d3)))
        if not FIRST <= first <= last < opening <= LAST or opening != last + timedelta(days=1):
            raise ValueError("inconsistent closure or reopening")
        closed.update(first + timedelta(days=i) for i in range((last-first).days + 1))
        reopen.add(opening)
    if closed & reopen:
        raise ValueError("conflicting closure and reopening")
    return closed, reopen


def ledger(raw, as_of):
    """The next-day rule is a date-only assumption, not first-publication proof."""
    as_of = day(as_of)
    closed, reopen = notice(raw)
    available = as_of > PUBLISHED
    rows = []
    for offset in range((LAST - FIRST).days + 1):
        session = FIRST + timedelta(days=offset)
        if not available:
            status = "UNKNOWN_AS_OF"
        elif session in closed:
            status = "NOTICE_HOLIDAY_CLOSED"
        elif session in reopen:
            status = "NOTICE_EXPLICIT_REOPEN"
        elif session.weekday() >= 5:
            status = "INFERRED_WEEKEND_CLOSED"
        else:
            status = "INFERRED_WEEKDAY_OPEN"
        rows.append({"market": "SZ", "day": session.isoformat(), "status": status,
                     "source_sha256": SHA if available else None})
    return {
        "status": "SCOPED_OFFICIAL_NOTICE_REPLAY_ONLY",
        "as_of_beijing_date": as_of.isoformat(), "source_url": SOURCE, "source_sha256": SHA,
        "displayed_publication_date": PUBLISHED.isoformat(),
        "earliest_research_use_date_assumed": (PUBLISHED + timedelta(days=1)).isoformat(),
        "first_publication_timestamp_authenticated": False,
        "full_historical_calendar_authenticated": False,
        "sse_original_available": False, "rows": rows,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def lookup(report, market, value):
    value = day(value).isoformat()
    return next((row["status"] for row in report["rows"]
                 if row["market"] == market and row["day"] == value), "UNKNOWN")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=FILE)
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    print(json.dumps(ledger(args.source.read_bytes(), args.as_of), ensure_ascii=False))


if __name__ == "__main__":
    main()
