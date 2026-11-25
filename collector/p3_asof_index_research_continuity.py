"""Recover *research leads only* from a pinned earlier official index artifact.

A current unavailable CNINFO query can use the last archived, source-SHA
identical query as a bounded PDF discovery hint. This does NOT turn a prior
response into a current successful query, a publication-time proof or an
exchange trading-status certification.
"""
import argparse
import copy
import json
import re
from pathlib import Path

SHA=re.compile(r"[0-9a-f]{64}\Z")
ISSUER=re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
PDF=re.compile(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/([0-9]+)\.PDF\Z",re.I)
PHASE="P3_THREE_ASOF_VENDOR_GAP_OFFICIAL_INDEX_RESEARCH"


def _check(snapshot, name):
    if (not isinstance(snapshot,dict) or snapshot.get("phase")!=PHASE
        or not isinstance(snapshot.get("source_epoch_sha256"),str)
        or not SHA.fullmatch(snapshot["source_epoch_sha256"])
        or snapshot.get("research_issuers")!=3
        or snapshot.get("historical_first_publication_authenticated") is not False
        or snapshot.get("independent_exchange_status_authenticated") is not False
        or snapshot.get("historical_PIT_verified") is not False
        or snapshot.get("trade_gate")!="BLOCKED"
        or snapshot.get("orders")!=[] or snapshot.get("executable_candidates")!=[]
        or snapshot.get("buy_signals")!=[]):
        raise ValueError("unsafe "+name+" research source")
    rows=snapshot.get("results")
    if not isinstance(rows,list) or len(rows)!=3:
        raise ValueError("invalid source issuer count")
    out={}
    for row in rows:
        issuer=row.get("issuer") if isinstance(row,dict) else None
        vendor=row.get("original_vendor_csv_sha256") if isinstance(row,dict) else None
        status=row.get("status") if isinstance(row,dict) else None
        docs=row.get("candidates") if isinstance(row,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or issuer in out or not isinstance(vendor,str) or not SHA.fullmatch(vendor)
            or not isinstance(docs,list) or len(docs)>90
            or status not in ("INDEX_CANDIDATES_UNVERIFIED",
                               "NO_INDEX_MATCH_NOT_NO_RISK",
                               "INDEX_UNAVAILABLE_NOT_NO_RISK")
            or row.get("official_asof_state_authenticated") is not False
            or row.get("independent_exchange_status_authenticated") is not False
            or (status=="INDEX_UNAVAILABLE_NOT_NO_RISK" and docs)
            or (status=="NO_INDEX_MATCH_NOT_NO_RISK" and docs)
            or (status=="INDEX_CANDIDATES_UNVERIFIED" and not docs)):
            raise ValueError("invalid source "+name+" issuer row")
        seen=set()
        for doc in docs:
            url=doc.get("official_pdf_url") if isinstance(doc,dict) else None
            m=PDF.fullmatch(url) if isinstance(url,str) else None
            ident=doc.get("announcement_id") if isinstance(doc,dict) else None
            if (m is None or ident!=m.group(1) or ident in seen
                or doc.get("historical_PIT_verified") is not False
                or doc.get("original_bytes_captured") is not False):
                raise ValueError("untrusted previous official index candidate")
            seen.add(ident)
        out[issuer]=row
    if snapshot.get("index_candidates")!=sum(len(r["candidates"]) for r in rows):
        raise ValueError("source candidate count mismatch")
    if snapshot.get("index_unavailable")!=sum(
            r["status"]=="INDEX_UNAVAILABLE_NOT_NO_RISK" for r in rows):
        raise ValueError("source unavailable count mismatch")
    return out


def recover(current,previous=None,previous_run_id=None):
    recent=_check(current,"current")
    older=_check(previous,"previous") if previous is not None else None
    if older is not None:
        if (type(previous_run_id) is not int or previous_run_id<=0
            or previous["source_epoch_sha256"]!=current["source_epoch_sha256"]
            or set(recent)!=set(older)):
            raise ValueError("cross-run historical source identity mismatch")
        for issuer,row in recent.items():
            prev=older[issuer]
            if any(row.get(k)!=prev.get(k) for k in (
                    "original_vendor_csv_sha256","vendor_asof_date",
                    "research_window_start","research_window_end")):
                raise ValueError("previous index issuer SHA or asof-window mismatch")
    rows=[]
    recovered=[]
    for issuer in sorted(recent):
        row=copy.deepcopy(recent[issuer])
        row["current_index_status"]=row["status"]
        row["current_index_was_unavailable"]=row["status"]=="INDEX_UNAVAILABLE_NOT_NO_RISK"
        row["research_leads_from_previous_run"]=False
        row["archived_research_source_run_id"]=None
        if (older is not None and row["current_index_was_unavailable"]
            and older[issuer]["status"]=="INDEX_CANDIDATES_UNVERIFIED"):
            row["candidates"]=copy.deepcopy(older[issuer]["candidates"])
            row["status"]="PREVIOUS_RUN_INDEX_LEADS_RESEARCH_ONLY"
            row["research_leads_from_previous_run"]=True
            row["archived_research_source_run_id"]=previous_run_id
            recovered.append(issuer)
        rows.append(row)
    effective={
        "phase":PHASE,
        "source_epoch_sha256":current["source_epoch_sha256"],
        "research_issuers":3,
        "index_candidates":sum(len(row["candidates"]) for row in rows),
        "index_unavailable":current["index_unavailable"],
        "current_index_candidates":current["index_candidates"],
        "previous_research_lead_issuers":len(recovered),
        "research_source_run_id":previous_run_id if older is not None else None,
        "results":rows,
        "historical_first_publication_authenticated":False,
        "independent_exchange_status_authenticated":False,
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"buy_signals":[],
    }
    return {
        "phase":"P3_ASOF_PINNED_INDEX_RESEARCH_CONTINUITY",
        "status":"PREVIOUS_RESEARCH_LEADS_NOT_CURRENT_QUERIES",
        "source_epoch_sha256":current["source_epoch_sha256"],
        "previous_artifact_run_id":previous_run_id if older is not None else None,
        "current_index_unavailable":current["index_unavailable"],
        "current_index_candidates":current["index_candidates"],
        "previous_research_lead_issuers":len(recovered),
        "previous_research_lead_codes":recovered,
        "effective_discovery":effective,
        "pdf_index_for_bounded_research":{
            "phase":"P3_REAL_P1_LIVE_INDEX_DISCOVERY",
            "trade_gate":"BLOCKED","historical_PIT_verified":False,
            "results":[{"issuer":row["issuer"],"status":row["status"],
                        "candidates":row["candidates"]}
                       for row in rows]},
        "historical_first_publication_authenticated":False,
        "independent_exchange_status_authenticated":False,
        "historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],"buy_signals":[],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--current",required=True,type=Path)
    p.add_argument("--previous",type=Path)
    p.add_argument("--previous-run",type=int)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    if (a.previous is None)!=(a.previous_run is None):
        raise ValueError("historical artifact path and run ID must be paired")
    previous=json.loads(a.previous.read_text()) if a.previous else None
    report=recover(json.loads(a.current.read_text()),previous,a.previous_run)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"current_unavailable":report["current_index_unavailable"],
        "previous_leads_recovered":report["previous_research_lead_issuers"],
        "trade_gate":"BLOCKED"}))


if __name__=="__main__":
    main()
