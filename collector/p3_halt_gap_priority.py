"""Prioritize SHA-bound vendor halt gaps without inferring official status."""
import argparse
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path


def prioritize(report):
    if (report.get("trade_gate") != "BLOCKED" or report.get("orders") != []
            or report.get("executable_candidates") != []
            or report.get("officially_certified_halt_dates") != 0
            or report.get("historical_PIT_trade_eligible") is not False):
        raise ValueError("unsafe source report")
    by_issuer = defaultdict(list)
    seen = set()
    count = 0
    for row in report["pending_official_evidence"]:
        code, day, digest = row["code"], row["target_date"], row["original_csv_sha256"]
        if (not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}", code)
                or date.fromisoformat(day).isoformat() != day
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or row.get("vendor_status") != "0"
                or row.get("official_effective_date_authenticated") is not False
                or row.get("official_publication_time_authenticated") is not False
                or row.get("official_source_url") is not None
                or row.get("official_source_sha256") is not None
                or row.get("risk_state") != "UNVERIFIED"):
            raise ValueError("invalid gap identity or certification")
        key = (code, day)
        if key in seen:
            raise ValueError("duplicate issuer day")
        seen.add(key)
        entries = row["affected_entry_dates"]
        if not isinstance(entries, list) or not entries or len(set(entries)) != len(entries):
            raise ValueError("missing or duplicate entry dates")
        if any(date.fromisoformat(x).isoformat() != x or x >= day for x in entries):
            raise ValueError("invalid entry chronology")
        count += len(entries)
        by_issuer[code].append(dict(target_date=day, original_csv_sha256=digest,
                                    affected_entry_dates=sorted(entries)))
    if len(seen) != report["distinct_issuer_halt_dates"] or count != report["vendor_suspended_exit_observations"]:
        raise ValueError("gap totals mismatch")
    tasks = []
    for code, rows in by_issuer.items():
        rows.sort(key=lambda x:x["target_date"])
        if len({r["original_csv_sha256"] for r in rows}) != 1:
            raise ValueError("multiple originals for one issuer in pinned epoch")
        tasks.append(dict(code=code, first_target=rows[0]["target_date"],
                          last_target=rows[-1]["target_date"], distinct_target_days=len(rows),
                          affected_entries=sum(len(r["affected_entry_dates"]) for r in rows),
                          targets=rows, required_evidence=["OFFICIAL_HALT_NOTICE","OFFICIAL_RESUME_NOTICE","FIRST_PUBLICATION_CLOCK"],
                          official_verified=False))
    tasks.sort(key=lambda x:(-x["affected_entries"],-x["distinct_target_days"],x["code"]))
    return dict(issuer_tasks=len(tasks), target_days=len(seen), affected_entries=count,
                tasks=tasks, officially_certified_halt_dates=0, trade_gate="BLOCKED",
                orders=[], executable_candidates=[])


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("report",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=prioritize(json.loads(a.report.read_bytes()))
    a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("PRIORITY_QUEUE:",json.dumps({k:v for k,v in r.items() if k!="tasks"},sort_keys=True))
