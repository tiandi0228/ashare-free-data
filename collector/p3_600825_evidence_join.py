"""Join issuer originals and disclosure index dates without promoting clock evidence."""
import argparse
import json
import re
from pathlib import Path

from collector.p3_600825_index_clock import EXPECTED, SOURCE, replay


def join(original, index):
    if (original["issuer"] != "sh.600825" or original["trade_gate"] != "BLOCKED"
        or original["orders"] != [] or original["executable_candidates"] != []
        or original["historical_PIT_verified"] is not False
        or original["pre_open_availability_verified"] is not False
        or original["entire_issuer_gap_closed"] is not False):
        raise ValueError("unsafe original replay boundary")
    clocks = {row["notice_id"]: row for row in replay(index)["rows"]}
    rows = {}
    for item in original["notices"]:
        match = re.fullmatch(r"https://static\.cninfo\.com\.cn/finalpage/(\d{4}-\d{2}-\d{2})/(\d+)\.PDF",
                             item["url"])
        if match is None:
            raise ValueError("invalid original notice URL")
        url_day, identifier = match.groups()
        if (identifier in rows or EXPECTED.get(identifier) != url_day
            or item["url_path_date_not_timestamp"] != url_day
            or item["first_publication_timestamp_verified"] is not False
            or not re.fullmatch(r"[a-f0-9]{64}", item["original_sha256"])):
            raise ValueError("original notice identity or evidence mismatch")
        rows[identifier] = {
            **clocks[identifier], "announcement_number": item["number"],
            "original_url": item["url"], "original_sha256": item["original_sha256"],
            "event_dates": item["event_dates"], "index_date_beijing": url_day,
        }
    if rows.keys() != clocks.keys():
        raise ValueError("incomplete original/index join")
    return {
        "status": "FOUR_ORIGINALS_JOINED_TO_INDEX_NO_OFFICIAL_RELEASE_PROOF",
        "issuer": original["issuer"], "rows": list(rows.values()),
        "secondary_visibility_lead": original["secondary_public_visibility_lead"],
        "matched_vendor_days": original["matched_days"], "official_first_release_count": 0,
        "historical_PIT_verified": False, "entire_issuer_gap_closed": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def markdown(result):
    lines = [
        "# 600825 披露时间对照",
        "",
        "| 公告编号 | 原件所述事件日期 | 北京时间索引值 | 官方首次披露 |",
        "|---|---|---|---|",
    ]
    for row in result["rows"]:
        events = " / ".join(row["event_dates"].values())
        lines.append(f'| {row["announcement_number"]} | {events} | {row["index_time_beijing"]} | 未认证 |')
    lines += ["", "索引值不是首发时间。媒体报道是公开消息旁证，不替代官方开盘前披露证据。",
              "", f'归档行情匹配 {result["matched_vendor_days"]} 天。整项缺口未关闭，交易门禁 BLOCKED。']
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    result = join(json.loads(args.original.read_bytes()), json.loads(SOURCE.read_bytes()))
    args.markdown.write_text(markdown(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
