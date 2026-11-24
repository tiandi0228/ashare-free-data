"""Select real GitHub Actions source artifacts, not success-only workflow runs.

A workflow can be 'success' while the evidence-producing job is skipped.
This resolver never certifies official/PIT status or triggers a vendor request.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

SOURCES = {
    "p2": ("p2-original-gap-window-triage.yml", "p2-original-gap-triage-"),
    "p3": ("p3-full-p1-official-scout.yml", "p3-full-p1-official-scout-"),
}


def choose_run(rows, artifact_lookup, prefix, preferred_id=None):
    """Return the newest successful non-PR run with a real unexpired artifact.

    The preferred triggering run is tried first, but is not implicitly valid;
    a skipped evidence job must not hide a genuine older artifact. The
    downstream P2/P3 source guard separately enforces current epoch/coverage.
    """
    if not isinstance(rows, list):
        raise ValueError("invalid GitHub run listing")
    seen = set()
    candidates = []
    for row in rows:
        if (not isinstance(row, dict) or type(row.get("databaseId")) is not int
                or row["databaseId"] <= 0):
            raise ValueError("invalid GitHub workflow run")
        if row["databaseId"] in seen:
            raise ValueError("duplicate GitHub workflow run")
        seen.add(row["databaseId"])
        if row.get("conclusion") == "success" and row.get("event") != "pull_request":
            candidates.append(row["databaseId"])
    candidates.sort(reverse=True)
    if preferred_id in candidates:
        candidates.remove(preferred_id)
        candidates.insert(0, preferred_id)
    for run_id in candidates:
        artifacts = artifact_lookup(run_id)
        if not isinstance(artifacts, list):
            raise ValueError("invalid GitHub artifacts response")
        exact = prefix + str(run_id)
        matched = [a for a in artifacts if isinstance(a, dict) and a.get("name") == exact
                   and a.get("expired") is False and type(a.get("size_in_bytes")) is int
                   and a["size_in_bytes"] > 0]
        if len(matched) > 1:
            raise ValueError("ambiguous source artifacts")
        if matched:
            return run_id
    raise ValueError("no successful non-expired evidence artifact found for " + prefix)


def resolve(list_runs, list_artifacts, triggered=None):
    """Resolve an exact artifact-backed source pair with provenance."""
    if triggered is not None:
        if (not isinstance(triggered, dict) or triggered.get("conclusion") != "success"
                or type(triggered.get("id")) is not int or triggered["id"] <= 0
                or triggered.get("name") not in (
                    "P2 original CSV 21-bar gap root-cause audit (NO TRADES)",
                    "P3 rotating official originals for full audited P1 issuer queue (NO TRADES)")):
            raise ValueError("unrecognized or unsuccessful upstream source run")
    result = {}
    for kind, (workflow, prefix) in SOURCES.items():
        rows = list_runs(workflow)
        preferred = None
        if triggered and ((kind == "p2" and triggered["name"].startswith("P2 original CSV"))
                          or (kind == "p3" and triggered["name"].startswith("P3 rotating"))):
            preferred = triggered["id"]
        result[kind + "_run_id"] = choose_run(rows, list_artifacts, prefix, preferred)
    result.update(status="ARTIFACT_BACKED_SOURCE_RUNS_RESEARCH_ONLY",
                  official_PIT_certified=False, trade_gate="BLOCKED", orders=[])
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--event", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", a.repo) is None:
        raise ValueError("invalid repository full name")

    def gh(*cmd):
        return json.loads(subprocess.check_output(["gh", *cmd], text=True, timeout=40))

    def list_runs(workflow):
        return gh("run", "list", "-R", a.repo, "--workflow", workflow,
                  "--limit", "100", "--json", "databaseId,conclusion,event")

    def list_artifacts(run_id):
        response = gh("api", f"repos/{a.repo}/actions/runs/{run_id}/artifacts",
                      "-f", "per_page=100", "--method", "GET")
        if not isinstance(response, dict):
            raise ValueError("invalid GitHub artifact listing")
        return response.get("artifacts")

    trigger = None
    if a.event:
        event = json.loads(a.event.read_text())
        trigger = event["workflow_run"]
    result = resolve(list_runs, list_artifacts, trigger)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print("P2/P3 verified actual source artifact availability:", {
        "p2_run_id": result["p2_run_id"], "p3_run_id": result["p3_run_id"],
        "trade_gate": "BLOCKED",
    })


if __name__ == "__main__":
    main()
