"""Read-only GitHub corroboration for a specific pre-window registration."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO = "tiandi0228/ashare-free-data"
RUN = 43404703610
JOB = 131816091344
HEAD = "e6d3a140e9f0dbc483e8087e90a4c9afe82919f2"
WORKFLOW = ".github/workflows/p4-prospective-registration.yml"
MANIFEST = "manifests/p4_prospective_20261201.json"
MANIFEST_DIGEST = "913889c977ede0d50bb5ecc5f78e0a3516b7d07d53ec4774065a0044dd6cbe0d"
API = f"https://api.github.com/repos/{REPO}"


def instant(raw):
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") != raw:
        raise ValueError("expected canonical UTC timestamp")
    return value


def verify(run, job, raw):
    doc = json.loads(raw)
    registration = doc["registration"]
    protocol = registration["protocol"]
    canonical = json.dumps(registration, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    if (doc["registration_sha256"] != MANIFEST_DIGEST
        or hashlib.sha256(canonical.encode()).hexdigest() != MANIFEST_DIGEST):
        raise ValueError("unexpected preregistered manifest")
    if (run["id"], run["head_sha"], run["path"], run["workflow_id"], run["event"],
        run["run_attempt"], run["status"], run["conclusion"], run["repository"]["full_name"]) != (
            RUN, HEAD, WORKFLOW, 417115300, "pull_request", 1, "completed", "success", REPO):
        raise ValueError("unexpected GitHub workflow identity or state")
    if (job["id"], job["run_id"], job["head_sha"], job["name"], job["status"], job["conclusion"]) != (
        JOB, RUN, HEAD, "verify-registration", "completed", "success"):
        raise ValueError("unexpected GitHub job identity or state")
    names = ("Validate frozen rules and time boundaries", "Independently reproduce registered baseline bytes")
    steps = [[s for s in job["steps"] if s["name"] == name] for name in names]
    if any(len(matches) != 1 or matches[0]["status"] != "completed"
           or matches[0]["conclusion"] != "success" for matches in steps):
        raise ValueError("required verification steps did not both succeed")
    declared = instant(protocol["claimed_created_at_utc"])
    cutoff = datetime.fromisoformat(protocol["window_start"] + "T00:00:00+08:00")
    observed = [instant(run["created_at"]), instant(run["run_started_at"]), instant(job["started_at"])]
    for matches in steps:
        observed.extend(instant(matches[0][key]) for key in ("started_at", "completed_at"))
    observed.append(instant(job["completed_at"]))
    if observed != sorted(observed) or not declared <= observed[0] <= observed[-1] < cutoff:
        raise ValueError("verification did not finish before the Beijing window")
    return {
        "status": "GITHUB_PREWINDOW_RUN_CORROBORATED_RESEARCH_ONLY",
        "registration_sha256": MANIFEST_DIGEST, "registration_commit": HEAD,
        "github_run_id": RUN, "github_job_id": JOB,
        "github_run_created_at": run["created_at"], "github_job_completed_at": job["completed_at"],
        "window_starts_beijing": cutoff.isoformat(),
        "window_ends_beijing_inclusive": protocol["window_end"],
        "sample_capture_started": False, "historical_OOS_validated": False,
        "prospective_OOS_validated": False, "historical_PIT_verified": False,
        "broker_fills_verified": 0, "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def get(url):
    req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "StockMate-P4-research"})
    with urlopen(req, timeout=20) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    raw = get(f"https://raw.githubusercontent.com/{REPO}/{HEAD}/{MANIFEST}")
    run = json.loads(get(f"{API}/actions/runs/{RUN}"))
    job = json.loads(get(f"{API}/actions/jobs/{JOB}"))
    report = verify(run, job, raw)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
