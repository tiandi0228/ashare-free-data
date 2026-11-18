"""Dated issuer source crosswalk and historical ST exclusion (research-only).

Original P2 CSVs are checked by the preceding workflow replay. Source PDF
references are reviewed issuer disclosures but the PDF bytes are not SHA-pinned
in this workflow; exact exchange dissemination/PIT state remains unverified.
"""
import argparse
import json
from pathlib import Path

EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
EXPECTED={
"sh.600363":("shard_0033","e4c01fa609951f30d25ec28ff729fa862c4815eca4ae279c9d7aeb1940f0fee2",1,"2026-09-29","2026-09-30","2026-09-30","ST联光",(("halt_st","2026-068","2026-09-29","1225584110"),)),
"sh.600825":("shard_0078","63ae1dd1502c2340aea79be6144a58d2256ed7edeb8c72b3bc69f289eb673e8a",8,"2026-10-13","2026-10-16",None,None,(("halt","2026-030","2026-10-13","1225602155"),("resume","2026-031","2026-10-16","1225607741"))),
"sh.603159":("shard_0137","c36cfc0437a88c63a3f63385a147c8f203cb0fc29ea5086dd71f32607bc24eb2",3,"2026-09-10","2026-09-17",None,None,(("resume","2026-026","2026-09-17","1225568804"),)),
"sh.605303":("shard_0208","6c96135604c6cacdccc054c0babd022c3ac21488ab1c3597c7628f763b653688",10,"2026-09-14","2026-09-29",None,None,(("halt","2026-040","2026-09-12","1225560951"),("resume","2026-043","2026-09-29","1225585581"))),
}

def reconcile(triage, sources):
    if (not isinstance(triage,dict)
        or triage.get("phase")!="P2_ORIGINAL_SHA_VERIFIED_FEATURE_GAP_RESEARCH_TRIAGE"
        or triage.get("source_epoch_sha256")!=EPOCH
        or triage.get("trade_gate")!="BLOCKED"
        or triage.get("historical_PIT_verified") is not False
        or triage.get("orders")!=[] or triage.get("executable_candidates")!=[]
        or triage.get("unresolved_issuers")!=16
        or triage.get("unresolved_shards")!=15
        or triage.get("feature_complete_shards")!=226
        or triage.get("observed_shards")!=241
        or triage.get("complete_feature_shards_promoted_by_triage")!=0):
        raise ValueError("untrusted original coverage")
    if (not isinstance(sources,dict)
        or sources.get("phase")!="P3_FOUR_ISSUER_DATED_SOURCE_REFERENCES_WITH_ST_GUARD"
        or sources.get("source_epoch_sha256")!=EPOCH
        or sources.get("source_documents_pdf_bytes_sha_verified") is not False
        or sources.get("official_full_pit_halt_calendar_certified") is not False
        or sources.get("st_trading_date_verified_via_issuer_notice_only") is not True
        or sources.get("historical_PIT_verified") is not False
        or sources.get("trade_gate")!="BLOCKED"
        or sources.get("orders")!=[] or sources.get("executable_candidates")!=[]):
        raise ValueError("issuer source provenance overpromoted")
    cases=sources.get("cases")
    original=triage.get("research_actions")
    if not isinstance(cases,list) or len(cases)!=4 or not isinstance(original,list) or len(original)!=16:
        raise ValueError("unexpected issuer count")
    original_by_code={x.get("issuer"):x for x in original}
    if len(original_by_code)!=16:
        raise ValueError("duplicate original issuer")
    found={}
    for case in cases:
        if not isinstance(case,dict):
            raise ValueError("invalid issuer case")
        code=case.get("issuer")
        if code not in EXPECTED or code in found:
            raise ValueError("unexpected or repeated issuer")
        shard, sha, halted, start, end, st_start, st_name, docs=EXPECTED[code]
        original_case=original_by_code.get(code)
        if (not isinstance(original_case,dict)
            or original_case.get("category")!="VENDOR_SUSPENDED_IN_LAST_21_ROWS"
            or original_case.get("shard_id")!=shard
            or original_case.get("original_csv_sha256")!=sha
            or original_case.get("suspended_rows_last_21")!=halted
            or original_case.get("gap_resolved") is not False
            or original_case.get("eligible_for_feature_complete_promotion") is not False
            or case.get("shard")!=shard
            or case.get("original_csv_sha256")!=sha
            or case.get("vendor_suspended_rows_last_21")!=halted
            or case.get("halt_start")!=start
            or case.get("resume_day")!=end
            or case.get("st_start")!=st_start
            or case.get("st_name")!=st_name):
            raise ValueError("P2 original or curated issuer case mismatch")
        references=case.get("documents")
        if not isinstance(references,list) or len(references)!=len(docs):
            raise ValueError("document count mismatch")
        for doc, (kind, notice, day, code_id) in zip(references,docs):
            if (not isinstance(doc,dict)
                or doc.get("kind")!=kind
                or doc.get("notice")!=notice
                or doc.get("date")!=day
                or doc.get("url")!=f"https://static.cninfo.com.cn/finalpage/{day}/{code_id}.PDF"):
                raise ValueError("document URL/notice identity changed")
        found[code]={
          "issuer":code,"P2_original_csv_sha256":sha,
          "curated_issuer_halt_start":start,"curated_issuer_resume_day":end,
          "risk_warning_st_effective_day":st_start,
          "issuer_notice_risk_name":st_name,
          "exclude_from_user_mainboard_nonST_strategy_from":st_start,
          "issuer_reference_count":len(docs),
          "issuer_notice_source_linked":True,
          "source_pdf_bytes_sha_verified":False,
          "full_historical_pit_tradability_certified":False,
          "gap_resolved":False,
        }
    if set(found)!=set(EXPECTED):
        raise ValueError("missing issuer sources")
    return {
        "phase":"P2_P3_FOUR_ISSUER_HALT_ST_CROSSWALK_RESEARCH_ONLY",
        "source_epoch_sha256":EPOCH,
        "new_issuer_sources_linked":4,
        "previous_issuer_sources_linked":3,
        "total_vendor_suspension_issuer_sources_linked":7,
        "remaining_vendor_suspension_issuers_without_source_links":8,
        "issuer_results":found,
        "st_risk_exclusion":{"issuer":"sh.600363","effective_from":"2026-09-30",
          "non_st_mainboard_screen_allowed_from_effective_day":False,
          "proof_scope":"ISSUER_DATED_DISCLOSURE_ONLY_NOT_EXCHANGE_PIT_AUTH"},
        "issuer_source_pdf_bytes_sha_verified":False,
        "historical_PIT_verified":False,
        "original_gap_issuers_unresolved":16,
        "original_gap_shards_unresolved":15,
        "feature_complete_shards":226,
        "observed_shards":241,
        "feature_shards_promoted":0,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--triage",type=Path,required=True)
    p.add_argument("--sources",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=reconcile(json.loads(a.triage.read_text()),json.loads(a.sources.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
      "phase","new_issuer_sources_linked","total_vendor_suspension_issuer_sources_linked",
      "remaining_vendor_suspension_issuers_without_source_links","feature_shards_promoted",
      "trade_gate")},sort_keys=True))
if __name__=="__main__":
    main()
