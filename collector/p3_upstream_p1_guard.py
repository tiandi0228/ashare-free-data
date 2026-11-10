"""Validate P3's upstream P1 workflow-run identity without trusting run-name.

GitHub Actions run-name changes the displayed name; workflow file path,
repository, branch and event are the actual provenance boundary.
Research-only: success does not certify official PIT or trading.
"""


def p1_upstream_run_id(upstream, expected_repo):
    if not isinstance(upstream, dict) or not isinstance(expected_repo, str):
        raise ValueError("untrusted upstream run")
    repository = upstream.get("head_repository")
    if (upstream.get("conclusion") != "success"
        or upstream.get("path") != ".github/workflows/p1-fresh-vendor-roster.yml"
        or not isinstance(repository, dict)
        or repository.get("full_name") != expected_repo
        or upstream.get("head_branch") != "main"
        or upstream.get("event") not in ("schedule", "push", "workflow_dispatch")
        or type(upstream.get("id")) is not int or upstream["id"] <= 0):
        raise ValueError("unexpected upstream P1 run")
    return upstream["id"]
