"""P3 600150 dated media crosscheck: research evidence, never PIT certification.

The source article day is not an authenticated first-publication instant.
Frozen issuer notices and PDF hashes are independently byte-replayed elsewhere.
"""
import json
from datetime import date

PINNED = {
    "1224387134": {
        "notice": "2025-059",
        "event": "HALT_START",
        "notice_day": "2025-08-05",
        "claimed_effective_day": "2025-08-13",
        "pdf_sha256": "498e48ccc9651e9be9e32dd17eaf60e2e9b9ed43fc8be41b26c995308561a66e",
        "media_url": "https://epaper.cs.com.cn/zgzqb/wap/html/2025-08/05/nw.D110000zgzqb_20250805_7-B044.htm",
        "secondary_url": "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=11278475&stockid=600150",
    },
    "1224504273": {
        "notice": "2025-063",
        "event": "RESUME_START",
        "notice_day": "2025-08-19",
        "claimed_effective_day": "2025-08-19",
        "pdf_sha256": "a529af260766407070b8d800cb890b26d06bee07adca3192244fe225546a1dbe",
        "media_url": "https://epaper.cs.com.cn/zgzqb/html/2025-08/19/nw.D110000zgzqb_20250819_6-B066.htm",
        "secondary_url": "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=11311275&stockid=600150",
    },
}


def build():
    rows = []
    for announcement, source in sorted(PINNED.items()):
        publication_day = date.fromisoformat(source["notice_day"])
        event_day = date.fromisoformat(source["claimed_effective_day"])
        if event_day < publication_day:
            raise ValueError("event claimed before notice date")
        rows.append({
            "issuer": "sh.600150",
            "announcement_id": announcement,
            "notice_number": source["notice"],
            "research_event": source["event"],
            "notice_date_claim_from_dated_public_page": publication_day.isoformat(),
            "effective_date_claim_from_issuer_notice": event_day.isoformat(),
            "original_pdf_sha256": source["pdf_sha256"],
            "dated_media_evidence_url": source["media_url"],
            "secondary_notice_index_url": source["secondary_url"],
            "publication_time_of_day_authenticated": False,
            "publisher_origin_independently_authenticated": False,
            "exchange_effective_interval_authenticated": False,
            "complete_historical_PIT_state_authenticated": False,
            "candidate_asof_trade_eligible": False,
            "remaining_evidence": [
                "VALIDATE_HISTORIC_MEDIA_PAGE_CONTENT_AND_ORIGINALS",
                "INDEPENDENT_FIRST_PUBLICATION_INSTANT_AND_TIMEZONE",
                "EXCHANGE_APPROVED_HALTED_SESSION_AND_RESUMPTION",
                "COMPLETE_ISSUER_BY_DAY_RISK_STATE",
            ],
        })
    return {
        "phase": "P3_600150_DATED_MEDIA_CROSSCHECK_RESEARCH",
        "historical_notice_days_crossreferenced": 2,
        "independently_authenticated_first_publication_instants": 0,
        "official_historical_PIT_verified": False,
        "rows": rows,
        "trade_gate": "BLOCKED",
        "orders": [],
        "executable_candidates": [],
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
