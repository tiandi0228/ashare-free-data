"""Cross-check four independently replayed real issuer documents; never infer PIT.

Two CNINFO PDF SHA receipts and two SSE HTML SHA receipts establish
repeatable bytes, not contemporaneous availability or full risk coverage.
"""
import argparse
import json
from pathlib import Path
from collector.p3_sse_official_receipt_gap import reconcile as sse_audit
from collector.p3_real_receipt_gap import reconcile as cninfo_audit

def audit(cninfo, sse, cninfo_replay, sse_replay):
    a=cninfo_audit(cninfo)
    b=sse_audit(sse)
    if cninfo_replay.get("phase")!="P3_TWO_CNINFO_ORIGINAL_PDF_REACQUISITION" or cninfo_replay.get("run_id")!=39703908661:
        raise ValueError("unrecognized CNINFO independent replay")
    if sse_replay.get("phase")!="P3_SSE_INDEPENDENT_TWO_PAGE_SHA_REPLAY" or sse_replay.get("second_run_id")!=39705092936:
        raise ValueError("unrecognized SSE independent replay")
    actual_pdf=[e.get("sha256") for e in cninfo_replay.get("sources",[])]
    actual_html=[e.get("sha256") for e in sse_replay.get("results",[])]
    if (len(actual_pdf)!=2 or len(actual_html)!=2 or
        actual_pdf!=cninfo.get("source_sha256") or
        actual_html!=[e["sha256"] for e in sse["pages"]] or
        any(e.get("independent_sha_match") is not True for e in cninfo_replay["sources"]) or
        any(e.get("matched") is not True for e in sse_replay["results"])):
        raise ValueError("cross-source original hash or independent replay mismatch")
    expected_pdf=[
      ("https://static.cninfo.com.cn/finalpage/2026-05-23/1225327963.PDF",244242),
      ("https://static.cninfo.com.cn/finalpage/2026-06-19/1225377517.PDF",109614),
    ]
    if any(e.get("url")!=u or e.get("bytes")!=size for e,(u,size) in zip(cninfo_replay["sources"],expected_pdf)):
        raise ValueError("CNINFO replay URL or size mismatch")
    if (sse_replay.get("first_run_id")!=39704160169
        or sse_replay.get("second_run_id")==sse_replay.get("first_run_id")
        or cninfo_replay.get("job_id")!=119579327490):
        raise ValueError("independent capture identity mismatch")
    for original,replay in zip(sse["pages"],sse_replay["results"]):
        if replay.get("url")!=original["url"] or replay.get("bytes")!=original["bytes"]:
            raise ValueError("SSE replay URL or size mismatch")
    if (cninfo_replay.get("trade_gate")!="BLOCKED" or sse_replay.get("trade_gate")!="BLOCKED" or
        cninfo_replay.get("historical_asof_publication_instant_verified") is not False or
        sse_replay.get("historical_publication_instant_verified") is not False):
        raise ValueError("research evidence promoted without PIT proof")
    return {
      "phase":"P3_CROSS_PUBLISHER_ORIGINAL_REPLAY_AUDIT",
      "issuer":"sh.600421",
      "independently_replayed_originals":4,
      "originals_by_publisher":{"CNINFO":2,"SSE":2},
      "independent_replay_SHA_match":True,
      "sse_effective_delist_announcement_date":"2026-06-22",
      "sse_announced_effective_delist_date":"2026-06-26",
      "cninfo_issuer_forecast_last_trade_day":"2026-06-22",
      "forecast_is_not_official_effective_delist_date":True,
      "historical_publication_instant_verified":False,
      "complete_historical_daily_status_verified":False,
      "cninfo_missing_PIT_cells":a["missing_evidence_cells"],
      "sse_missing_PIT_cells":b["missing_evidence_cells"],
      "evidence_layers":{
        "original_source_bytes_same_at_two_observation_times":True,
        "official_SSE_delist_notice_observed":True,
        "issuer_CNINFO_notice_observed":True,
        "historical_publication_instant_proven":False,
        "all_ST_halt_listing_intervals_proven":False,
        "historical_point_in_time_membership_proven":False,
        "P4_out_of_sample_strategy_passed":False
      },
      "current_use":"SOURCE_PROVENANCE_RESEARCH_ONLY",
      "missing_acceptance_requirements":[
        "HISTORICAL_PUBLICATION_TIMESTAMPS",
        "OFFICIAL_DAILY_LISTING_ST_HALT_DELIST_INTERVALS",
        "FULL_MAINBOARD_HISTORICAL_UNIVERSE",
        "DURABLE_REPLAYABLE_ORIGINALS_WITH_PERMITTED_RETENTION",
        "P4_OUT_OF_SAMPLE_AND_EXECUTION_VALIDATION"
      ],
      "historical_risk_coverage_complete":False,
      "raw_source_durably_archived":False,
      "data_redistribution_licensed":False,
      "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"paid_api_calls":0
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    def load(n):return json.loads((Path("reports")/n).read_text("utf-8"))
    r=audit(
      load("p3_600421_two_pdf_event_chain_20261021.json"),
      load("p3_sse_two_official_original_sha_observed_20261022.json"),
      load("p3_cninfo_two_pdf_independent_sha_recapture_20261022.json"),
      load("p3_sse_independent_two_originals_verified_20261022.json"))
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"matched":r["independently_replayed_originals"],"gate":r["trade_gate"]}))
if __name__=="__main__":main()
