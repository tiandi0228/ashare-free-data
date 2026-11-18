"""Replay scoped secondary observations, not an official release clock."""
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlsplit

BEIJING = timezone(timedelta(hours=8))
SCOPES = {"ROUNDUP_OMISSION", "REPORTS_INITIAL_AND_CONTINUED_HALT", "EFFECTIVE_INTERVAL_ONLY"}


def clock(value):
    parsed = datetime.fromisoformat(value)
    if "T" not in value or parsed.utcoffset() != BEIJING.utcoffset(None):
        raise ValueError("expected explicit Beijing date and time")
    return parsed


def audit(source, notice):
    if (source["issuer"], source["notice_id"], notice["notice_id"],
            notice["announcement_number"]) != ("sh.600825", "1225552231", "1225552231", "2026-014"):
        raise ValueError("September clock source/notice mismatch")
    event_dates = notice["event_dates"]
    if event_dates != {"retrospective_halt_start": "2026-09-07", "continued_halt": "2026-09-08"}:
        raise ValueError("September halt clauses do not match pinned original")
    initial, continued = (datetime.combine(date.fromisoformat(event_dates[k]), time(9, 15), BEIJING)
                          for k in ("retrospective_halt_start", "continued_halt"))
    rows, seen, leads = [], set(), []
    for row in source["observations"]:
        scope = row["scope"]
        url = urlsplit(row["url"])
        if scope not in SCOPES or url.scheme != "https" or not url.hostname or row["url"] in seen:
            raise ValueError("unsupported or duplicate September clock observation")
        seen.add(row["url"])
        displayed = row["displayed_time"]
        if scope == "EFFECTIVE_INTERVAL_ONLY":
            if displayed is not None:
                raise ValueError("effective interval must not supply a display clock")
            if clock(row["effective_start"]).date() != initial.date():
                raise ValueError("effective interval does not match initial halt day")
            first, continuation = ("NO_PUBLICATION_CLOCK",) * 2
        elif scope == "ROUNDUP_OMISSION":
            clock(displayed)
            first, continuation = ("OMISSION_NOT_PROOF",) * 2
        else:
            stamp = clock(displayed)
            if stamp < initial:
                first = "SECONDARY_BEFORE_AUCTION_REQUIRES_REVIEW"
            elif stamp.date() == initial.date() and stamp.time() < time(15):
                first = "NOT_BEFORE_AUCTION"
            else:
                first = "RETROSPECTIVE_ONLY"
            continuation = "SCOPED_SECONDARY_BEFORE_AUCTION" if stamp < continued else "NOT_BEFORE_AUCTION"
            if stamp < continued:
                leads.append(stamp)
        rows.append({**row, "initial_halt_classification": first,
                     "continued_halt_classification": continuation})
    return {
        "notice_id": source["notice_id"], "initial_auction_beijing": initial.isoformat(),
        "continuation_auction_beijing": continued.isoformat(), "observations": rows,
        "initial_halt_before_auction_verified": False,
        "earliest_reviewed_continuation_media_time": min(leads).isoformat() if leads else None,
        "official_first_release_verified": False,
    }
