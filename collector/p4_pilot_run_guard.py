"""Fail-closed read-only GitHub run and same-day artifact guard."""
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from collector.p4_prospective_daily_capture import eligible_day, BEIJING

REPO = "tiandi0228/ashare-free-data"


def verify(now, expected_day, run_id, run, artifacts):
    day = eligible_day(now)
    if day is None or day != expected_day:
        raise ValueError("outside approved capture day")
    if (type(run.get("id")) is not int or run["id"] != run_id
            or run.get("head_branch") != "main"
            or run.get("event") not in ("schedule", "workflow_dispatch")
            or run.get("repository", {}).get("full_name") != REPO):
        raise ValueError("unexpected workflow run")
    created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    if created.utcoffset() is None or created > now or created.astimezone(BEIJING).date().isoformat() != day:
        raise ValueError("cross-day or invalid run clock")
    if (type(artifacts.get("total_count")) is not int or artifacts["total_count"] < 0
            or not isinstance(artifacts.get("artifacts"), list)
            or artifacts["total_count"] != len(artifacts["artifacts"])):
        raise ValueError("incomplete artifact inventory")
    name = "p4-prospective-" + day
    if any(not isinstance(a, dict) or a.get("name") != name for a in artifacts["artifacts"]):
        raise ValueError("unexpected artifact inventory")
    return {"day": day, "allowed": artifacts["total_count"] == 0,
            "status": "NO_PRIOR_NAMED_ARTIFACT" if not artifacts["total_count"] else "DUPLICATE_DAY_SKIPPED",
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": []}


def main():
    token = os.environ["GH_TOKEN"]
    run_id = int(os.environ["GITHUB_RUN_ID"])
    day = os.environ["EXPECTED_DAY"]
    def get(path):
        req = Request("https://api.github.com/repos/" + REPO + path,
                      headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=20) as response:
            return json.load(response)
    run = get("/actions/runs/" + str(run_id))
    artifacts = get("/actions/artifacts?" + urlencode({"name": "p4-prospective-" + day, "per_page": 100}))
    report = verify(datetime.now(timezone.utc), day, run_id, run, artifacts)
    print(json.dumps(report, sort_keys=True))
    with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
        print("day=" + (day if report["allowed"] else ""), file=handle)


if __name__ == "__main__":
    main()
