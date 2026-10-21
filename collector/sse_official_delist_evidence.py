"""Two bounded direct SSE documents: decision date != actual delisting date.

The output is a researched *official-host page observation*, not publisher-signed,
complete historical point-in-time issuer state. No strategy or trade signals.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

COMPANY = "湖北华嵘控股股份有限公司"
ISSUER = "sh.600421"
SOURCES = (
    {
        "url": "https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260522_10819392.shtml",
        "event": "DELIST_DECISION_ONLY",
        "publication_date": "2026-05-22",
        "effective_delist_date": None,
        "needles": (COMPANY, "2026-05-22", "本所决定终止" + COMPANY + "股票上市"),
    },
    {
        "url": "https://www.sse.com.cn/disclosure/announcement/listing/stock/c/c_20260622_10823158.shtml",
        "event": "DELIST_EFFECTIVE_DATE_ANNOUNCED",
        "publication_date": "2026-06-22",
        "effective_delist_date": "2026-06-26",
        "needles": (COMPANY, "2026-06-22", "600421", "2026年6月26日对其予以摘牌"),
    },
)
MAX_BYTES = 750_000


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.tokens.append(data)


def fetch_document(url):
    """One HTTPS GET, 12 second timeout, no retries or alternate sources."""
    req = Request(url, headers={"User-Agent": "ashare-free-data-research-source-audit/1.0",
                                "Accept-Encoding": "identity"})
    with urlopen(req, timeout=12) as resp:
        if resp.geturl() != url:
            raise ValueError("Unexpected redirect or source origin")
        raw = resp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Official page exceeded byte budget")
        return raw, resp.geturl()


def inspect_document(spec, raw, final_url):
    if final_url != spec["url"] or not final_url.startswith("https://www.sse.com.cn/"):
        raise ValueError("Source URL did not match frozen SSE path")
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Missing or oversized official HTML")
    # Avoid trusting a bot challenge or an unrelated HTML page.
    parsed = VisibleHTML()
    parsed.feed(raw.decode("utf-8"))
    clean = re.sub(r"\s+", "", "".join(parsed.tokens))
    for needle in spec["needles"]:
        if needle not in clean:
            raise ValueError("Frozen document evidence anchor missing")
    next_day = (datetime.strptime(spec["publication_date"], "%Y-%m-%d")
                + timedelta(days=1)).date().isoformat()
    return {
        "issuer": ISSUER,
        "official_host_observed": True,
        "page_content_sha256": hashlib.sha256(raw).hexdigest(),
        "page_content_bytes": len(raw),
        "source_url": final_url,
        "event": spec["event"],
        "page_publication_date_no_intraday_timestamp": spec["publication_date"],
        "conservative_next_calendar_day_for_review": next_day,
        "effective_delist_date": spec["effective_delist_date"],
        "original_html_not_redistributed": True,
        "publisher_digital_signature_verified": False,
        "original_publication_timestamp_independently_verified": False,
    }


def capture(out, fetch=fetch_document):
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": "P3_SSE_TWO_OFFICIAL_HOST_DELISTING_PAGES",
        "status": "BLOCKED_PARTIAL",
        "issuer": ISSUER,
        "logical_https_get_budget": 2,
        "attempted_gets": 0,
        "page_events": [],
        "source_publisher_digitally_authenticated": False,
        "complete_historical_ST_halt_and_delist_verified": False,
        "historical_point_in_time_universe_verified": False,
        "issuer_tradability_certified": False,
        "historical_decision_time_verified": False,
        "paid_api_calls": 0,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }
    for spec in SOURCES:
        outcome = {"event": spec["event"], "status": "ERROR", "url": spec["url"]}
        report["attempted_gets"] += 1
        try:
            raw, final_url = fetch(spec["url"])
            outcome.update(inspect_document(spec, raw, final_url))
            outcome["status"] = "OBSERVED_OFFICIAL_HOST_UNVERIFIED_PUBLICATION_TIMING"
        except (ValueError, OSError, TimeoutError, UnicodeError) as err:
            outcome["failure_type"] = type(err).__name__
        report["page_events"].append(outcome)
    if all(e["status"] == "OBSERVED_OFFICIAL_HOST_UNVERIFIED_PUBLICATION_TIMING"
           for e in report["page_events"]):
        assert (report["page_events"][0]["effective_delist_date"] is None
                and report["page_events"][1]["effective_delist_date"] == "2026-06-26")
        report["status"] = "TWO_OFFICIAL_HOST_DOCUMENTS_OBSERVED_NO_PIT_CERTIFICATION"
    report["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    (dest / "quality.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"].startswith("TWO_OFFICIAL") else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    raise SystemExit(capture(args.out))
