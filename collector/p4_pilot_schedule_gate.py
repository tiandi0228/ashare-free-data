"""Read-only vendor calendar gate for optional scheduled pilot, never exchange certification."""
import argparse
import json
import os
from datetime import datetime, timezone

from collector.p4_prospective_daily_capture import eligible_day

FIELDS = ["calendar_date", "is_trading_day"]


def check(now, provider, *, enabled):
    day = eligible_day(now)
    report = dict(day=day, allowed=False, status="DISABLED_OR_OUTSIDE_WINDOW",
                  vendor_calendar_row=None, official_session_verified=False,
                  trade_gate="BLOCKED", orders=[], executable_candidates=[])
    if enabled is not True or day is None:
        return report
    client = provider()
    if client.login().error_code != "0":
        raise RuntimeError("vendor calendar login failed")
    try:
        result = client.query_trade_dates(start_date=day, end_date=day)
        if result.error_code != "0" or list(result.fields) != FIELDS or not result.next():
            raise ValueError("missing or invalid vendor calendar")
        row = list(result.get_row_data())
        if (len(row) != 2 or row[0] != day or row[1] not in ("0", "1")
                or result.next() or result.error_code != "0"):
            raise ValueError("ambiguous vendor calendar")
        report.update(vendor_calendar_row=row, allowed=row[1]=="1",
                      status="VENDOR_SESSION_ONLY" if row[1]=="1" else "VENDOR_CLOSED")
        return report
    finally:
        client.logout()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enabled", action="store_true")
    args=parser.parse_args()
    def provider():
        import baostock
        return baostock
    report=check(datetime.now(timezone.utc), provider, enabled=args.enabled)
    print(json.dumps(report,sort_keys=True))
    with open(os.environ["GITHUB_OUTPUT"],"a") as handle:
        print("day="+(report["day"] if report["allowed"] else ""),file=handle)


if __name__=="__main__":
    main()
