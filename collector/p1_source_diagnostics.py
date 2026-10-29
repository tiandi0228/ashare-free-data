"""Read-only P1 per-shard vendor diagnostics; preserves failed research evidence.

A green Actions job is not proof of a new shard. This diagnostic records the
observed provider response and bounded failure categories without modifying
checkpoints, archived CSVs, credentials, or the blocked trading gate.
"""
import argparse
import json
import os
from pathlib import Path

ROLES = ("first_shard", "second_shard", "third_shard", "fourth_shard", "repair_shard")
MAX_ERRORS = 8


def _read(path):
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict):
            raise ValueError("not a JSON object")
        return item, None
    except (OSError, UnicodeError, ValueError, TypeError):
        return None, "INVALID_OR_UNREADABLE_JSON"


def _role_requests(root):
    selection_path = root / "pilot_selection.json"
    selection, error = _read(selection_path) if selection_path.exists() else (None, None)
    selected = selection.get("selected_count") if selection else None
    if type(selected) is not int or not 1 <= selected <= 2:
        selected = None
    repair_path = root / "repair_pick.json"
    repair, _ = _read(repair_path) if repair_path.exists() else (None, None)
    requested_repair = bool(repair and repair.get("repair_shard") is not None)
    return {
        "first_shard": selected is None or selected >= 1,
        "second_shard": selected is not None and selected >= 2,
        "third_shard": False,
        "fourth_shard": False,
        "repair_shard": requested_repair,
    }


def examine(root):
    root = Path(root)
    requested = _role_requests(root)
    results = []
    for role in ROLES:
        folder = root / role
        quality_path = folder / "quality.json"
        timeout_path = folder / "runner_timeout.json"
        row = {
            "role": role, "requested": requested[role],
            "status": "NOT_PRODUCED" if requested[role] else "NOT_REQUESTED",
            "issuer_count": None, "queries_attempted": None,
            "observed_issuers": 0, "failed_issuers": 0,
            "failure_categories": [], "failed_codes": [],
        }
        if timeout_path.exists():
            timeout, err = _read(timeout_path)
            if err or timeout.get("trade_gate") != "BLOCKED":
                row["status"] = "INVALID_TIMEOUT_EVIDENCE"
            elif type(timeout.get("exit_code")) is not int:
                row["status"] = "INVALID_TIMEOUT_EVIDENCE"
            else:
                row["runner_timeout_exit_code"] = timeout["exit_code"]
                row["status"] = "RUNNER_TIMEOUT"
        if quality_path.exists():
            receipt, err = _read(quality_path)
            if err:
                row["status"] = "INVALID_SOURCE_RECEIPT"
                row["failure_categories"] = [err]
            elif receipt.get("trade_gate") != "BLOCKED":
                row["status"] = "UNSAFE_SOURCE_RECEIPT"
                row["failure_categories"] = ["TRADE_GATE_NOT_BLOCKED"]
            else:
                row["source_status"] = str(receipt.get("status", "UNKNOWN"))[:96]
                row["issuer_count"] = receipt.get("issuer_count")
                row["queries_attempted"] = receipt.get("query_attempts")
                sources = receipt.get("results")
                if not isinstance(sources, list) or len(sources) > 8:
                    row["status"] = "INVALID_SOURCE_RECEIPT"
                    row["failure_categories"] = ["INVALID_ISSUER_RESULTS"]
                else:
                    failures = []
                    for item in sources:
                        if not isinstance(item, dict):
                            failures.append({"code": "UNKNOWN", "reason": "INVALID_ISSUER_RESULT"})
                        elif item.get("status") == "OBSERVED_UNVERIFIED":
                            row["observed_issuers"] += 1
                        else:
                            failures.append({
                                "code": str(item.get("code", "UNKNOWN"))[:32],
                                "reason": str(item.get(
                                    "failure_category",
                                    item.get("error_type", "SOURCE_ERROR")))[:96],
                            })
                    row["failed_issuers"] = len(failures)
                    row["failed_codes"] = failures[:MAX_ERRORS]
                    categories = sorted(set(x["reason"] for x in failures))
                    if receipt.get("failure_category"):
                        categories.append(str(receipt["failure_category"])[:96])
                    if receipt.get("login_error_type"):
                        categories.append("LOGIN_" + str(receipt["login_error_type"])[:80])
                    if row["source_status"] == "OBSERVED_SUBSET_UNVERIFIED" and not failures and sources:
                        row["status"] = "OBSERVED_UNVERIFIED"
                    elif row["status"] != "RUNNER_TIMEOUT":
                        row["status"] = "SOURCE_INCOMPLETE"
                    row["failure_categories"] = sorted(set(categories))[:MAX_ERRORS]
        results.append(row)
    progress_path = root / "p1_run_progress.json"
    progress, error = _read(progress_path) if progress_path.exists() else (None, None)
    status = progress.get("status") if progress and progress.get("trade_gate") == "BLOCKED" else None
    return {
        "phase": "P1_SHARD_SOURCE_DIAGNOSTICS",
        "trade_gate": "BLOCKED",
        "historical_PIT_verified": False,
        "archival_progress_status": status if isinstance(status, str) else "UNAVAILABLE",
        "roles": results,
        "orders": [],
        "executable_candidates": [],
    }


def summary_lines(report):
    lines = ["", "### P1 per-shard vendor acquisition diagnosis",
             "", "| Research shard | Requested | Source result | Observed / failed |",
             "| --- | --- | --- | --- |"]
    for item in report["roles"]:
        name = item["role"].replace("_", " ")
        lines.append(
            f"| {name} | {'yes' if item['requested'] else 'no'} | "
            f"{item['status']} | {item['observed_issuers']} / {item['failed_issuers']} |"
        )
        for detail in item["failed_codes"]:
            lines.append(
                f"- {name}: `{detail['code']}` — {detail['reason']}"
            )
        if item["failure_categories"]:
            lines.append(
                f"- {name} categories: {', '.join(item['failure_categories'])}"
            )
    lines += [
        "", f"Archived progress report: **{report['archival_progress_status']}**.",
        "No vendor observation or green workflow authorizes trading.",
    ]
    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="evidence")
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    args = parser.parse_args()
    report = examine(args.evidence)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.summary_file:
        with Path(args.summary_file).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(summary_lines(report)) + "\n")
    print(json.dumps({
        "phase": report["phase"],
        "archival_progress_status": report["archival_progress_status"],
        "roles": [
            {"role": item["role"], "status": item["status"],
             "failed_issuers": item["failed_issuers"]}
            for item in report["roles"]
        ],
        "trade_gate": "BLOCKED",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
