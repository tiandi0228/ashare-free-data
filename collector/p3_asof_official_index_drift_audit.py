"""Bounded independent cross-run CNINFO index *metadata* drift audit.

Two SHA-bound research snapshots can disagree about an announcement's index
timestamp, PDF link or title. A stable metadata value is still NOT independent
first-publication, listing or exchange effective-state evidence.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from collector.p3_asof_index_research_continuity import _check

MAX_ISSUERS=3
MAX_NOTICES=270

def _candidates(row):
    return {doc["announcement_id"]:doc for doc in row["candidates"]}

def compare(current,previous,previous_run_id):
    now=_check(current,"current")
    before=_check(previous,"prior")
    if (type(previous_run_id) is not int or previous_run_id<=0
        or current["source_epoch_sha256"]!=previous["source_epoch_sha256"]
        or len(now)!=MAX_ISSUERS or set(now)!=set(before)):
        raise ValueError("unpaired research source epochs")
    evidence=[]
    reviewed=Counter()
    for issuer in sorted(now):
        recent=now[issuer]
        older=before[issuer]
        if any(recent.get(k)!=older.get(k) for k in (
            "original_vendor_csv_sha256","vendor_asof_date",
            "research_window_start","research_window_end")):
            raise ValueError("cross-run issuer/source SHA/window changed")
        a=_candidates(recent)
        b=_candidates(older)
        usable_a=recent["status"]=="INDEX_CANDIDATES_UNVERIFIED"
        usable_b=older["status"]=="INDEX_CANDIDATES_UNVERIFIED"
        if usable_a and usable_b:
            for notice in sorted(set(a)|set(b)):
                one=a.get(notice)
                two=b.get(notice)
                if one is None:
                    verdict="PRIOR_ONLY_INDEX_MATCH_NOT_DELETION_PROOF"
                elif two is None:
                    verdict="CURRENT_ONLY_INDEX_MATCH_NOT_NEW_PUBLICATION_PROOF"
                else:
                    if one.get("official_pdf_url")!=two.get("official_pdf_url"):
                        verdict="SAME_NOTICE_PDF_URL_CHANGED_REVIEW_REQUIRED"
                    elif one.get("index_published_milliseconds_unverified")!=two.get("index_published_milliseconds_unverified"):
                        verdict="SAME_NOTICE_INDEX_TIME_CHANGED_REVIEW_REQUIRED"
                    elif one.get("announcement_title_unverified")!=two.get("announcement_title_unverified"):
                        verdict="SAME_NOTICE_TITLE_CHANGED_REVIEW_REQUIRED"
                    else:
                        verdict="SAME_NOTICE_INDEX_METADATA_STABLE_NOT_PUBLICATION_PROOF"
                reviewed[verdict]+=1
                evidence.append({
                    "issuer":issuer,"announcement_id":notice,
                    "original_vendor_csv_sha256":recent["original_vendor_csv_sha256"],
                    "current_index_status":recent["status"],
                    "prior_index_status":older["status"],
                    "current_index_pdf_url":one.get("official_pdf_url") if one else None,
                    "prior_index_pdf_url":two.get("official_pdf_url") if two else None,
                    "current_index_milliseconds_unverified":one.get("index_published_milliseconds_unverified") if one else None,
                    "prior_index_milliseconds_unverified":two.get("index_published_milliseconds_unverified") if two else None,
                    "metadata_comparison":verdict,
                    "prior_source_run_id":previous_run_id,
                    "authenticated_first_publication":False,
                    "certified_exchange_state":False,
                    "historical_PIT_verified":False,
                })
        else:
            status=("CURRENT_INDEX_UNAVAILABLE_NO_COMPARISON" if not usable_a
                    else "PRIOR_INDEX_UNAVAILABLE_NO_COMPARISON")
            reviewed[status]+=1
            evidence.append({
                "issuer":issuer,"announcement_id":None,
                "original_vendor_csv_sha256":recent["original_vendor_csv_sha256"],
                "current_index_status":recent["status"],
                "prior_index_status":older["status"],
                "current_index_pdf_url":None,"prior_index_pdf_url":None,
                "current_index_milliseconds_unverified":None,
                "prior_index_milliseconds_unverified":None,
                "metadata_comparison":status,"prior_source_run_id":previous_run_id,
                "authenticated_first_publication":False,
                "certified_exchange_state":False,"historical_PIT_verified":False,
            })
    if len(evidence)>MAX_NOTICES:
        raise ValueError("unbounded cross-run notice comparisons")
    return {
        "phase":"P3_ASOF_CROSS_RUN_OFFICIAL_INDEX_METADATA_DRIFT",
        "status":"INDEX_DISCOVERY_METADATA_NOT_OFFICIAL_PUBLICATION_PROOF",
        "source_epoch_sha256":current["source_epoch_sha256"],
        "prior_source_run_id":previous_run_id,
        "issuers_in_scope":MAX_ISSUERS,
        "comparison_rows":len(evidence),
        "comparison_class_counts":dict(sorted(reviewed.items())),
        "rows":evidence,
        "authenticated_first_publication_count":0,
        "certified_exchange_intervals":0,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"buy_signals":[],
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--current",type=Path,required=True)
    parser.add_argument("--previous",type=Path,required=True)
    parser.add_argument("--previous-run",type=int,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    report=compare(json.loads(a.current.read_text()),
                   json.loads(a.previous.read_text()),a.previous_run)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"rows":report["comparison_rows"],
        "class_counts":report["comparison_class_counts"],
        "authenticated":0,"trade_gate":"BLOCKED"}))

if __name__=="__main__":
    main()
