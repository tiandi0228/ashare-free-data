"""P1 source-run scheduler ownership pre-write gate (STAGING ONLY, NO TRADES).

A future production cutover must put a shared, immutable generation fence
at the *collector write boundary*, not rely only on a backup scheduler
checking GitHub's visible queue. This module makes explicit fail-closed
decisions on a signed-by-blob SHA, versioned scheduler ownership document.

Not wired into production P1 workflow or external worker. Calling
evaluate() alone performs no I/O, no writes, no workflow dispatch.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

PHASE="P1_SHARED_SCHEDULER_OWNERSHIP_PREWRITE_STAGING"
EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
WORKFLOW=".github/workflows/p1-fresh-vendor-roster.yml"
OWNERS=frozenset(("NATIVE_ONLY","FREEZE_ALL","EXTERNAL_ONLY"))
GIT_SHA=re.compile(r"[0-9a-f]{40}\Z")
SHA256=re.compile(r"[0-9a-f]{64}\Z")
EVENTS=frozenset(("schedule","workflow_dispatch"))
ISO_TIME="%Y-%m-%dT%H:%M:%SZ"

def _time(value):
    if not isinstance(value,str) or not value.endswith("Z"):
        raise ValueError("non-UTC or missing timestamp")
    try:
        parsed=dt.datetime.strptime(value,ISO_TIME).replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ValueError("noncanonical UTC timestamp") from exc
    if parsed.strftime(ISO_TIME)!=value:raise ValueError("noncanonical timestamp")
    return parsed

def evaluate(contract,run,*,contract_blob_sha,contract_bytes_sha256,contract_raw_bytes):
    def block(reason):
        return {"phase":PHASE,"decision":"BLOCK","reason":reason,
            "source_epoch_sha256":EPOCH,
            "production_installation_verified":False,
            "external_dispatch_authorized":False,
            "collector_write_authorized":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
    if (not isinstance(contract_blob_sha,str) or not GIT_SHA.fullmatch(contract_blob_sha)
        or not isinstance(contract_bytes_sha256,str)
        or not SHA256.fullmatch(contract_bytes_sha256)):
        return block("CONTRACT_IMMUTABLE_BYTES_IDENTITY_MISSING")
    if not isinstance(contract_raw_bytes,bytes):
        return block("RAW_CONTRACT_BYTES_UNAVAILABLE")
    try:
        decoded=json.loads(contract_raw_bytes)
    except (ValueError,UnicodeError):
        return block("RAW_CONTRACT_BYTES_UNPARSABLE")
    if decoded!=contract:
        return block("RAW_CONTRACT_CONTENT_MISMATCH")
    if hashlib.sha256(contract_raw_bytes).hexdigest()!=contract_bytes_sha256:
        return block("RAW_CONTRACT_SHA256_MISMATCH")
    git_blob=b"blob "+str(len(contract_raw_bytes)).encode()+bytes([0])+contract_raw_bytes
    if hashlib.sha1(git_blob).hexdigest()!=contract_blob_sha:
        return block("RAW_CONTRACT_GIT_BLOB_SHA_MISMATCH")
    if not isinstance(contract,dict) or not isinstance(run,dict):
        return block("MALFORMED_CONTRACT_OR_RUN")
    if (contract.get("phase")!="P1_SHARED_SCHEDULER_OWNERSHIP_V1"
        or contract.get("source_epoch_sha256")!=EPOCH
        or contract.get("trade_gate")!="BLOCKED"
        or contract.get("orders")!=[]
        or contract.get("executable_candidates")!=[]
        or contract.get("allow_write_before_fence_confirmation") is not False):
        return block("CONTRACT_SOURCE_EPOCH_OR_SAFETY_INVALID")
    generation=contract.get("generation")
    if type(generation) is not int or generation<1:
        return block("INVALID_SCHEDULER_OWNERSHIP_GENERATION")
    owner=contract.get("owner")
    if owner not in OWNERS:
        return block("UNKNOWN_SCHEDULER_OWNER")
    try:
        created=_time(run.get("run_created_at_utc"))
        observed=_time(run.get("ownership_checked_at_utc"))
        active_from=_time(contract.get("effective_from_utc"))
    except ValueError:
        return block("INVALID_RUN_OR_CONTRACT_UTC_TIMESTAMP")
    if created>observed or observed-active_from<dt.timedelta(0):
        return block("NONCAUSAL_OWNERSHIP_TIMELINE")
    if observed-created>dt.timedelta(days=2):
        return block("STALE_RUN_CONTEXT")
    if (run.get("source_epoch_sha256")!=EPOCH
        or run.get("workflow_path")!=WORKFLOW
        or run.get("branch")!="main"
        or run.get("run_event") not in EVENTS
        or type(run.get("run_id")) is not int or run["run_id"]<1
        or type(run.get("run_attempt")) is not int or run["run_attempt"]<1
        or not isinstance(run.get("head_sha"),str)
        or not GIT_SHA.fullmatch(run["head_sha"])
        or run.get("observed_contract_generation")!=generation
        or run.get("observed_contract_blob_sha")!=contract_blob_sha
        or run.get("observed_contract_bytes_sha256")!=contract_bytes_sha256):
        return block("RUN_PROVENANCE_OR_OWNERSHIP_GENERATION_MISMATCH")
    if owner=="FREEZE_ALL":
        return block("CUTOVER_FREEZE_BLOCKS_ALL_P1_WRITES")
    if owner=="EXTERNAL_ONLY":
        # A future external writer needs its own certified identity and
        # separate implementation; old native scheduled/manual runs cannot
        # be granted by this native collector guard.
        return block("EXTERNAL_OWNER_NATIVE_SOURCE_VETO")
    # Even in NATIVE_ONLY phase a recovery/manual event is blocked by
    # default. Separate operator-authorized recovery is not implemented.
    if run["run_event"]!="schedule":
        return block("MANUAL_DISPATCH_UNAUTHORIZED_IN_NATIVE_ONLY")
    if run.get("native_schedule_currently_enabled") is not True:
        return block("NATIVE_CRON_ENABLED_STATUS_NOT_AUTHENTICATED")
    if created<active_from:
        return block("OLD_RUN_CREATED_BEFORE_ACTIVE_GENERATION")
    return {"phase":PHASE,"decision":"NATIVE_SCHEDULED_RUN_RESEARCH_ELIGIBLE",
        "reason":"NATIVE_GENERATION_MATCH_RESEARCH_ONLY",
        "source_epoch_sha256":EPOCH,
        "scheduler_generation":generation,
        "contract_blob_sha":contract_blob_sha,
        "contract_bytes_sha256":contract_bytes_sha256,
        "production_installation_verified":False,
        "external_dispatch_authorized":False,
        "collector_write_authorized":False,
        "source_write_preflight_would_pass_if_integrated":True,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for key in ("contract","run","out"):
        p.add_argument("--"+key,required=True,type=Path)
    p.add_argument("--contract-blob-sha",required=True)
    p.add_argument("--contract-bytes-sha256",required=True)
    a=p.parse_args()
    result=evaluate(json.loads(a.contract.read_text()),
                    json.loads(a.run.read_text()),
                    contract_blob_sha=a.contract_blob_sha,
                    contract_bytes_sha256=a.contract_bytes_sha256,
                    contract_raw_bytes=a.contract.read_bytes())
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":result["phase"],"decision":result["decision"],
        "reason":result["reason"],"actual_write_authorized":False,
        "trade_gate":"BLOCKED"},ensure_ascii=False))
if __name__=="__main__":main()
