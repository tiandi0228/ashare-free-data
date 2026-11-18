"""P3 research-only official publication proof gaps for two pinned 600150 PDF originals.

Inputs are a research capture receipt, NOT independently authenticated timestamps.
No download time, URL path date, PDF metadata or text date can become PIT proof.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SOURCE_COMMIT = "5be9d6ad76d8635defe02f8d90bc50ad4c03c086"
CSV_SHA = "45bb1574dc7068d696d74bfb74491984a9c792444396f3be6f04abe295ed7c40"
PDFS = {
    "1224387134": {
        "role": "halt", "number": "2025-059",
        "url": "https://static.cninfo.com.cn/finalpage/2025-08-05/1224387134.PDF",
        "sha256": "498e48ccc9651e9be9e32dd17eaf60e2e9b9ed43fc8be41b26c995308561a66e",
        "bytes": 92093,
    },
    "1224504273": {
        "role": "resume", "number": "2025-063",
        "url": "https://static.cninfo.com.cn/finalpage/2025-08-19/1224504273.PDF",
        "sha256": "a529af260766407070b8d800cb890b26d06bee07adca3192244fe225546a1dbe",
        "bytes": 89199,
    },
}
REQUIRED_GAPS = (
    "INDEPENDENT_OFFICIAL_PUBLISHER_ORIGIN",
    "AUTHENTICATED_HISTORICAL_FIRST_PUBLICATION_INSTANT",
    "EXCHANGE_EFFECTIVE_HALT_RESUME_INTERVAL",
    "COMPLETE_HISTORICAL_ISSUER_DAY_STATE",
)


def _utc_observed(value):
    if not isinstance(value, str) or not value:
        raise ValueError("missing capture timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("capture timezone missing")
    return parsed.astimezone(timezone.utc).isoformat()


def queue(receipt):
    if not isinstance(receipt, dict):
        raise ValueError("missing research receipt")
    for key, value in {
        "phase": "P3_600150_TWO_CNINFO_ORIGINAL_RESEARCH_ACQUISITION",
        "source_issuer": "sh.600150",
        "frozen_vendor_source_commit": SOURCE_COMMIT,
        "frozen_vendor_csv_sha256": CSV_SHA,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
        "research_only_not_certified": True,
        "originals_in_immutable_git_archive": False,
        "official_first_publication_authenticated": False,
        "official_halt_resume_interval_certified": False,
        "official_historical_PIT_verified": False,
        "trading_calendar_verified": False,
    }.items():
        if type(receipt.get(key)) is not type(value) or receipt[key] != value:
            raise ValueError("unsupported or promoted upstream evidence: " + key)
    if (type(receipt.get("documents_attempted")) is not int
            or receipt["documents_attempted"] != 2
            or type(receipt.get("documents_pdf_sha_replayed")) is not int
            or receipt["documents_pdf_sha_replayed"] != 2
            or type(receipt.get("broker_fills_verified")) is not int
            or receipt["broker_fills_verified"] != 0):
        raise ValueError("invalid upstream counts or fills")
    docs = receipt.get("documents")
    if not isinstance(docs, list) or len(docs) != 2:
        raise ValueError("missing original receipt rows")
    found = {}
    for row in docs:
        if not isinstance(row, dict):
            raise ValueError("invalid original receipt row")
        ident = row.get("announcement_id")
        if ident not in PDFS or ident in found:
            raise ValueError("unexpected/duplicate announcement")
        expected = PDFS[ident]
        for key, value in {
            "issuer": "sh.600150",
            "document_role": expected["role"],
            "notice_number_claimed": expected["number"],
            "requested_url": expected["url"],
            "pdf_sha256": expected["sha256"],
            "original_pdf_bytes": expected["bytes"],
            "status": "ORIGINAL_BYTES_SHA_REPLAY_VERIFIED_RESEARCH_ONLY",
            "original_artifact_path": (
                f"originals/sh_600150_{ident}_{expected['sha256']}.pdf"),
            "first_publication_authenticated": False,
            "official_publisher_authenticated_independently": False,
            "historical_effective_date_authenticated": False,
        }.items():
            if type(row.get(key)) is not type(value) or row[key] != value:
                raise ValueError("untrusted original identity or promoted proof: " + key)
        found[ident] = _utc_observed(row.get("observed_utc"))
    if set(found) != set(PDFS):
        raise ValueError("incomplete announcement identities")
    tasks = []
    for ident in sorted(PDFS):
        original = PDFS[ident]
        tasks.append({
            "issuer": "sh.600150",
            "announcement_id": ident,
            "document_role_research_only": original["role"],
            "notice_number_claimed_not_certified": original["number"],
            "original_pdf_sha256": original["sha256"],
            "original_pdf_bytes": original["bytes"],
            "source_url_research_locator": original["url"],
            "capture_observed_utc_not_first_publication": found[ident],
            "missing_official_proofs": list(REQUIRED_GAPS),
            "publisher_independently_authenticated": False,
            "historical_first_publication_authenticated": False,
            "exchange_effective_interval_certified": False,
            "historical_PIT_verified": False,
            "trade_eligible": False,
        })
    return {
        "phase": "P3_600150_OFFICIAL_PUBLICATION_AND_STATE_GAP_QUEUE",
        "source_frozen_commit": SOURCE_COMMIT,
        "frozen_vendor_csv_sha256": CSV_SHA,
        "research_original_count": len(tasks),
        "official_publication_instants_authenticated": 0,
        "official_state_intervals_certified": 0,
        "proof_tasks": tasks,
        "historical_PIT_verified": False,
        "trade_gate": "BLOCKED", "orders": [], "executable_candidates": [],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    outcome = queue(json.loads(args.research_receipt.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"phase": outcome["phase"], "tasks": len(outcome["proof_tasks"]),
                      "trade_gate": "BLOCKED"}, sort_keys=True))
