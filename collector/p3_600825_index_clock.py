"""Classify observed CNINFO timestamps without promoting them to first release."""
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path("evidence/p3_600825_index/cninfo-selected.json")
ENDPOINT = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
BEIJING = ZoneInfo("Asia/Shanghai")
EXPECTED = {
    "1225552231": "2026-09-08", "1225571469": "2026-09-19",
    "1225602155": "2026-10-13", "1225607741": "2026-10-16",
}


def replay(receipt):
    if (receipt["issuer"] != "sh.600825" or receipt["endpoint"] != ENDPOINT
        or receipt["scope"] != "SELECTED_FIELDS_NOT_RAW_RESPONSE"):
        raise ValueError("unexpected index receipt scope")
    results = []
    seen = set()
    for row in receipt["rows"]:
        identifier = row["announcement_id"]
        if identifier not in EXPECTED or identifier in seen:
            raise ValueError("unexpected or duplicate notice identity")
        seen.add(identifier)
        expected = EXPECTED[identifier]
        if row["official_pdf_url"] != f"https://static.cninfo.com.cn/finalpage/{expected}/{identifier}.PDF":
            raise ValueError("notice PDF URL mismatch")
        millis = row["index_published_milliseconds_unverified"]
        if type(millis) is not int or not 10**12 <= millis < 2 * 10**12:
            raise ValueError("invalid announcementTime")
        observed = datetime.fromtimestamp(millis / 1000, BEIJING)
        if observed.date().isoformat() != expected:
            raise ValueError("index and URL dates differ")
        results.append({
            "notice_id": identifier, "index_epoch_milliseconds": millis,
            "index_time_beijing": observed.isoformat(),
            "classification": ("MIDNIGHT_DATE_LABEL_ONLY" if observed.time() == time()
                               else "INDEX_CLOCK_FIELD_NOT_FIRST_RELEASE_PROOF"),
            "official_first_release": None, "official_preopen_visibility_verified": False,
        })
    if seen != EXPECTED.keys():
        raise ValueError("incomplete target notice coverage")
    return {
        "status": "INDEX_FIELDS_REPLAYED_NO_OFFICIAL_FIRST_RELEASE_PROOF",
        "rows": results, "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


if __name__ == "__main__":
    print(json.dumps(replay(json.loads(SOURCE.read_bytes())), ensure_ascii=False, indent=2))
