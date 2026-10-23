"""P3 official halt evidence gap manifest derived from SHA-checked P4 archives.

Vendor 'tradestatus=0' is a claim to investigate, not proof of an
official halt. Duplicated issuer/day observations are consolidated.
"""
import argparse,json
from pathlib import Path
from collector.p4_real_exit_availability import audit

def build(root):
    source=audit(root)
    by_target={}
    for item in source["vendor_halt_crosscheck_queue"]:
        key=(item["code"],item["target_exit_date"])
        record=by_target.setdefault(key,{"code":key[0],"target_date":key[1],
            "affected_entry_dates":[],"vendor_status":"0",
            "official_source_url":None,"official_source_sha256":None,
            "official_effective_date_authenticated":False,
            "official_publication_time_authenticated":False,
            "risk_state":"UNVERIFIED"})
        record["affected_entry_dates"].append(item["entry_date"])
    manifest=sorted(by_target.values(),key=lambda r:(r["code"],r["target_date"]))
    observed=sum(len(x["affected_entry_dates"]) for x in manifest)
    if observed!=source["target_vendor_suspended"]:raise ValueError("halt observation reconciliation mismatch")
    return {"phase":"P3_P4_REAL_HALT_EVIDENCE_GAPS",
        "source_verified_issuers":source["verified_issuers"],
        "vendor_suspended_exit_observations":observed,
        "distinct_issuer_halt_dates":len(manifest),
        "officially_certified_halt_dates":0,
        "pending_official_evidence":manifest,
        "vendor_status_is_not_official_halt_proof":True,
        "no_result_is_not_a_clean_risk_status":True,
        "historical_PIT_trade_eligible":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    p=argparse.ArgumentParser();p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=build(a.root);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="pending_official_evidence"},ensure_ascii=False))
if __name__=="__main__":main()
