"""Daily source reliability evidence from immutable snapshot index entries. NO TRADES.

This is a finite sample of GitHub Actions executions, not market-wide uptime,
provider SLA or executable price verification.
"""
from collections import Counter
from collector.intraday_snapshot_archive import WATCHLIST

def source_health(entries):
    if not isinstance(entries,list) or not entries:
        raise ValueError("missing indexed snapshot entries")
    result={}
    for code in sorted(WATCHLIST):
        attempts=len(entries)
        success=0
        failures=0
        max_failure_streak=0
        streak=0
        sources=Counter()
        error_types=Counter()
        issue_counts=Counter()
        prev_status=None
        recoveries=0
        last_failure_run=None
        latest_status=None
        for entry in entries:
            if not isinstance(entry,dict) or not isinstance(entry.get("symbols"),dict):
                raise ValueError("invalid indexed entry")
            row=entry["symbols"].get(code)
            if not isinstance(row,dict):
                raise ValueError("missing indexed symbol")
            status=row.get("status")
            if status=="SOURCE_UNAVAILABLE":
                failures+=1;streak+=1
                max_failure_streak=max(max_failure_streak,streak)
                last_failure_run=entry["run_id"]
                sources[row.get("error_stage") or "UNKNOWN"]+=1
                error_types[row.get("error_type") or "UNAVAILABLE"]+=1
            elif status=="RESEARCH_ONLY":
                success+=1;streak=0
                if prev_status=="SOURCE_UNAVAILABLE":recoveries+=1
                issues=row.get("quality_issues")
                if not isinstance(issues,list) or any(not isinstance(x,str) for x in issues):
                    raise ValueError("invalid quality issues")
                issue_counts.update(set(issues))
            else:
                raise ValueError("invalid source status")
            latest_status=status
            prev_status=status
        result[code]={
            "samples":attempts,
            "research_snapshots":success,
            "source_failures":failures,
            "observed_sample_success_ratio":round(success/attempts,6),
            "failure_stages":dict(sorted(sources.items())),
            "error_types":dict(sorted(error_types.items())),
            "quality_issue_samples":dict(sorted(issue_counts.items())),
            "max_consecutive_sample_failures":max_failure_streak,
            "consecutive_failures_at_latest_sample":streak,
            "recoveries_after_failed_sample":recoveries,
            "last_failed_run":last_failure_run,
            "latest_status":latest_status,
            "provider_sla_certified":False,
            "cross_source_price_verified":False,
            "trade_gate":"BLOCKED",
        }
    return result
