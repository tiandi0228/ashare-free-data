"""Cross-reference vendor suspension gaps against original PDF research leads.

Issuer matches are leads, not proof of historical interval, halt causation,
or correct first publication. No data repair, PIT promotion or trading.
"""
import argparse
import json
import re
from pathlib import Path

ISSUER_RE = re.compile(r"(?:sh|sz)\.\d{6}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

def valid_issuer(value):
    return isinstance(value,str) and ISSUER_RE.fullmatch(value) is not None

def crosswalk(gaps,events,pairs):
    if (gaps.get("phase")!="P2_ORIGINAL_CSV_GAP_WINDOW_DIAGNOSIS"
        or gaps.get("status")!="SOURCE_VERIFIED_VENDOR_WINDOW_RESEARCH_ONLY"
        or gaps.get("trade_gate")!="BLOCKED"
        or gaps.get("historical_PIT_verified") is not False
        or gaps.get("coverage_gaps_resolved")!=0
        or gaps.get("orders")!=[]
        or events.get("phase")!="P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH"
        or events.get("trade_gate")!="BLOCKED"
        or events.get("historical_PIT_verified") is not False
        or events.get("official_PIT_cells_certified")!=0
        or events.get("complete_issuer_halt_intervals_certified") is not False
        or events.get("historical_first_publication_authenticated") is not False
        or events.get("orders")!=[]
        or pairs.get("phase")!="P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS"
        or pairs.get("trade_gate")!="BLOCKED"
        or pairs.get("historical_PIT_verified") is not False
        or pairs.get("official_halt_resume_intervals_certified")!=0
        or pairs.get("authenticated_first_publication_count")!=0
        or pairs.get("orders")!=[]):
        raise ValueError("untrusted research source")
    gap_rows=gaps.get("results")
    event_rows=events.get("research_text_event_claims")
    pair_rows=pairs.get("text_only_halt_resume_pairs")
    if (not isinstance(gap_rows,list) or len(gap_rows)!=gaps.get("research_gap_issuers")
        or not isinstance(event_rows,list)
        or not isinstance(pair_rows,list)
        or len(pair_rows)!=pairs.get("deduplicated_research_text_pairs")):
        raise ValueError("unreconciled source research rows")
    by_issuer={}
    for row in event_rows:
        if (not isinstance(row,dict)
            or row.get("first_publication_authenticated") is not False
            or row.get("effective_date_certified") is not False
            or row.get("historical_asof_trade_eligible") is not False
            or not valid_issuer(row.get("issuer"))
            or row.get("textual_direction") not in ("HALT_START","RESUME_START","OTHER")):
            raise ValueError("unsafe historic event claim")
        by_issuer.setdefault(row["issuer"],[]).append(row)
    pair_index={}
    for row in pair_rows:
        if (not isinstance(row,dict)
            or row.get("historical_first_publication_verified") is not False
            or row.get("official_resume_effective_date_verified") is not False
            or row.get("whole_interval_tradability_verified") is not False
            or not valid_issuer(row.get("issuer"))):
            raise ValueError("unsafe text pair")
        pair_index.setdefault(row["issuer"],[]).append(row)
    examined=set()
    output=[]
    for row in gap_rows:
        code=row.get("issuer")
        if not valid_issuer(code) or code in examined:
            raise ValueError("duplicated gap issuer")
        examined.add(code)
        if (row.get("official_halt_explanation_authenticated") is not False
            or not isinstance(row.get("original_csv_sha256"),str)
            or SHA256_RE.fullmatch(row["original_csv_sha256"]) is None
            or not isinstance(row.get("asof_date"),str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",row["asof_date"])
            or type(row.get("trailing_vendor_suspended_rows")) is not int
            or not 0 <= row["trailing_vendor_suspended_rows"] <= 21):
            raise ValueError("gap source wrongly claims official certification")
        diagnosis=row.get("diagnosis")
        if diagnosis not in ("VENDOR_SUSPENDED_ROW_WITHIN_LAST_21","FEWER_THAN_21_VENDOR_ROWS_ASOF"):
            raise ValueError("unrecognized gap")
        original_event=by_issuer.get(code,[])
        related=[x for x in original_event if x["textual_direction"] in ("HALT_START","RESUME_START")]
        if related:
            status="SAME_ISSUER_P3_TEXT_LEAD_ONLY_NOT_EVENT_CAUSATION"
        else:
            status="NO_SAME_ISSUER_P3_HALT_TEXT_IN_BOUNDED_RESEARCH"
        output.append({
            "issuer":code,"vendor_gap_diagnosis":diagnosis,
            "asof_date":row["asof_date"],
            "vendor_trailing_suspended_rows":row["trailing_vendor_suspended_rows"],
            "vendor_csv_sha256":row["original_csv_sha256"],
            "same_issuer_official_pdf_text_leads":len(related),
            "same_issuer_sha_linked_resume_text_pairs":len(pair_index.get(code,[])),
            "evidence_association":status,
            "official_trading_state_covered_for_gap":False,
            "gap_resolved":False})
    with_lead=sum(x["same_issuer_official_pdf_text_leads"]>0 for x in output)
    with_pair=sum(x["same_issuer_sha_linked_resume_text_pairs"]>0 for x in output)
    return {
        "phase":"P2_P3_SAME_ISSUER_RESEARCH_GAP_CROSSWALK",
        "status":"RESEARCH_JOIN_NO_PIT_EVENT_CAUSATION",
        "gap_issuers_examined":len(output),
        "gap_issuers_with_same_issuer_official_pdf_text_lead":with_lead,
        "gap_issuers_with_same_issuer_resume_text_pair":with_pair,
        "official_halt_intervals_authenticated":0,
        "feature_gaps_resolved":0,
        "issuer_evidence":output,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
        "actionable_buy_signals":[]}

def main():
    p=argparse.ArgumentParser()
    for key in ("p2_gap_triage","p3_event_episodes","p3_pairs","out"):
        p.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    report=crosswalk(json.loads(a.p2_gap_triage.read_text()),
                     json.loads(a.p3_event_episodes.read_text()),
                     json.loads(a.p3_pairs.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in (
        "status","gap_issuers_examined",
        "gap_issuers_with_same_issuer_official_pdf_text_lead",
        "gap_issuers_with_same_issuer_resume_text_pair",
        "official_halt_intervals_authenticated","feature_gaps_resolved","trade_gate"
    )},ensure_ascii=False))
if __name__=="__main__":main()
