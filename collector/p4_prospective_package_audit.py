"""Independently audit a downloaded P4 GitHub Actions evidence ZIP offline."""
import argparse
import hashlib
import json
import re
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from collector.p2_independent_bars import audit_csv
from collector.p4_prospective_daily_capture import (
    CODES, END, REGISTRATION, START, verify_receipt,
)

PREFIX = "p4-prospective-capture"
EVIDENCE = "p4-prewindow-evidence.json"
PROOF_RUN = 43404703610
PROOF_JOB = 131816091344
PROOF_COMMIT = "e6d3a140e9f0dbc483e8087e90a4c9afe82919f2"
MAX_FILE = 64 * 1024


def audit(package, expected_day):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", expected_day):
        raise ValueError("expected YYYY-MM-DD Beijing date")
    folder = f"{PREFIX}/{expected_day}"
    names = {code.replace(".", "_") + ".csv" for code in CODES} | {"receipt.json"}
    allowed = {EVIDENCE} | {f"{folder}/{name}" for name in names}
    allowed_dirs = {f"{PREFIX}/", f"{folder}/"}
    with TemporaryDirectory() as tmp, Path(package).open("rb") as source:
        with ZipFile(source) as archive:
            seen = set()
            target = Path(tmp) / expected_day
            target.mkdir()
            for item in archive.infolist():
                name = item.filename
                kind = stat.S_IFMT(item.external_attr >> 16)
                if (name in seen or item.orig_filename != name or item.file_size > MAX_FILE
                    or (name not in allowed and name not in allowed_dirs)):
                    raise ValueError("unexpected, duplicate or oversized evidence member")
                seen.add(name)
                if item.is_dir():
                    if kind not in (0, stat.S_IFDIR) or item.file_size != 0:
                        raise ValueError("invalid evidence directory")
                    continue
                if kind not in (0, stat.S_IFREG) or name not in allowed:
                    raise ValueError("non-regular evidence member")
                data = archive.read(item)
                if name == EVIDENCE:
                    proof = json.loads(data)
                else:
                    (target / name.rsplit("/", 1)[1]).write_bytes(data)
            if EVIDENCE not in seen or f"{folder}/receipt.json" not in seen:
                raise ValueError("missing registration evidence or capture receipt")
        required = {
            "status": "GITHUB_PREWINDOW_RUN_CORROBORATED_RESEARCH_ONLY",
            "registration_sha256": REGISTRATION,
            "registration_commit": PROOF_COMMIT,
            "github_run_id": PROOF_RUN,
            "github_job_id": PROOF_JOB,
            "window_starts_beijing": START.isoformat() + "T00:00:00+08:00",
            "window_ends_beijing_inclusive": END.isoformat(),
            "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        }
        if (not isinstance(proof, dict) or any(proof.get(k) != v for k, v in required.items())
            or any(proof.get(k) is not False for k in (
                "prospective_OOS_validated", "historical_PIT_verified", "historical_OOS_validated"))):
            raise ValueError("registration evidence does not match the frozen pilot")
        receipt = verify_receipt(target)
        suspended, active, missing = [], [], []
        for entry in receipt["rows"]:
            code = entry["code"]
            if entry["status"] == "NO_VENDOR_ROW":
                missing.append(code)
                continue
            stats = audit_csv((target / entry["filename"]).read_bytes(), code)
            (suspended if stats["vendor_suspended_rows"] else active).append(code)
        source.seek(0)
        package_sha = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "status": "PILOT_PACKAGE_VERIFIED" if not missing else "PILOT_PACKAGE_VERIFIED_WITH_GAPS",
        "beijing_day": expected_day, "package_sha256": package_sha,
        "registration_sha256": REGISTRATION, "expected_issuers": len(CODES),
        "verified_vendor_rows": len(active) + len(suspended),
        "vendor_active_issuers": active, "vendor_suspended_issuers": suspended,
        "missing_vendor_issuers": missing, "pilot_complete": not missing,
        "github_origin_independently_verified": False,
        "official_session_verified": False, "prospective_OOS_validated": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--day", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.package, args.day), sort_keys=True))


if __name__ == "__main__":
    main()
