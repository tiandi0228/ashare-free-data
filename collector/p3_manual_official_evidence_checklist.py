"""Export 24-issuer P3 manual official-evidence checklist from SHA-bound research.

This is a review worksheet, NOT issuer historical status authentication.
Never infer official first-publication times from PDF text or download times.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{64}\Z")
ISSUER = re.compile(r"(?:sh|sz)\.[0-9]{6}\Z")
ASOF_ACTION = "VERIFY_ASOF_NONTRADABLE_EXCHANGE_AND_OFFICIAL_NOTICE"
ASOF_GAP = "VENDOR_MARKED_NOT_TRADABLE_AT_ASOF"


def export(queue, provenance):
    if (not isinstance(queue, dict)
        or queue.get("phase") != "P2_P3_SOURCE_SHA_ISSUER_EVIDENCE_REVIEW_QUEUE"
        or queue.get("status") != "UNRESOLVED_OFFICIAL_PROOF_REQUIREMENTS_RESEARCH_ONLY"
        or queue.get("trade_gate") != "BLOCKED"
        or queue.get("historical_PIT_verified") is not False
        or queue.get("feature_gaps_resolved") != 0
        or queue.get("official_halt_intervals_certified") != 0
        or queue.get("orders") != []
        or not isinstance(provenance, dict)
        or provenance.get("phase") != "P3_GAP_ISSUER_ORIGINAL_PDF_PROVENANCE_REVIEW_INDEX"
        or provenance.get("status") != "SHA_SOURCE_LOCATORS_ONLY_NO_FIRST_PUBLICATION_PROOF"
        or provenance.get("trade_gate") != "BLOCKED"
        or provenance.get("historical_PIT_verified") is not False
        or provenance.get("authenticated_first_publication_count") != 0
        or provenance.get("certified_exchange_intervals") != 0
        or provenance.get("orders") != []):
        raise ValueError("P3 manual evidence export requires uncertified no-trade sources")
    epoch = queue.get("source_epoch_sha256")
    if (not isinstance(epoch, str) or not SHA.fullmatch(epoch)
        or provenance.get("source_epoch_sha256") != epoch
        or queue.get("p2_source_run_id") != provenance.get("p2_source_run_id")
        or queue.get("p3_source_run_id") != provenance.get("p3_source_run_id")):
        raise ValueError("cross-epoch or cross-run review source")
    tasks, indexed = queue.get("tasks"), provenance.get("issuers")
    if (not isinstance(tasks, list) or not isinstance(indexed, list)
        or not 1 <= len(tasks) <= 400
        or queue.get("gap_issuer_count") != len(tasks)
        or queue.get("unresolved_issuer_count") != len(tasks)
        or provenance.get("gap_issuer_count") != len(indexed)):
        raise ValueError("truncated or inconsistent P3 review queue")
    by_issuer = {}
    for item in indexed:
        issuer = item.get("issuer") if isinstance(item,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or issuer in by_issuer
            or item.get("source_epoch_sha256") != epoch
            or item.get("official_first_publication_verified") is not False
            or item.get("complete_official_state_interval_certified") is not False
            or item.get("feature_gap_resolved") is not False
            or item.get("buy_eligible") is not False):
            raise ValueError("forged or duplicate P3 source issuer")
        by_issuer[issuer] = item
    rows = []
    seen = set()
    for task in tasks:
        issuer = task.get("issuer") if isinstance(task,dict) else None
        if (not isinstance(issuer,str) or not ISSUER.fullmatch(issuer)
            or issuer in seen or issuer not in by_issuer
            or task.get("source_epoch_sha256") != epoch
            or task.get("official_evidence_authenticated") is not False
            or task.get("historical_PIT_verified") is not False
            or task.get("feature_gap_resolved") is not False
            or task.get("buy_eligible") is not False):
            raise ValueError("unsafe or duplicate P3 manual proof task")
        seen.add(issuer)
        item = by_issuer[issuer]
        sha = task.get("original_vendor_csv_sha256")
        needs = task.get("required_official_evidence")
        docs = item.get("original_halt_resume_text_documents")
        pairs = item.get("original_resume_research_text_pairs")
        if (not isinstance(sha,str) or not SHA.fullmatch(sha)
            or item.get("vendor_csv_sha256") != sha
            or task.get("research_action") != item.get("research_action")
            or not isinstance(needs,list) or not needs
            or len(set(needs)) != len(needs)
            or not all(isinstance(v,str) and v for v in needs)
            or not isinstance(docs,list) or not isinstance(pairs,list)
            or len(docs) != task.get("official_pdf_halt_resume_text_leads")
            or len(pairs) != task.get("research_text_resume_pairs")):
            raise ValueError("review task and original PDF index mismatch")
        if task.get("vendor_gap_diagnosis") == ASOF_GAP:
            if (task.get("research_action") != ASOF_ACTION
                or "INDEPENDENT_ASOF_EXCHANGE_TRADING_STATUS" not in needs):
                raise ValueError("as-of nontradable issuer lacks exchange source requirement")
        locators = []
        for doc in docs:
            digest = doc.get("original_pdf_sha256") if isinstance(doc,dict) else None
            path = doc.get("original_sha_verified_archive_path") if isinstance(doc,dict) else None
            notice = doc.get("announcement_id") if isinstance(doc,dict) else None
            if (not isinstance(digest,str) or not SHA.fullmatch(digest)
                or not isinstance(notice,str) or not notice.isdigit()
                or path != f"pdf/{issuer.replace('.', '_')}/{notice}/{digest}.pdf"
                or doc.get("historical_first_publication_authenticated") is not False
                or doc.get("source_text_is_not_official_interval_proof") is not True):
                raise ValueError("invalid original PDF SHA locator")
            locators.append(f"{notice}:{digest}:{path}")
        canonical = json.dumps({"epoch":epoch,"issuer":issuer,"vendor_sha":sha,
            "action":task["research_action"],"documents":locators,
            "needed":needs},sort_keys=True,ensure_ascii=False,separators=(",",":"))
        rows.append({
            "review_id": hashlib.sha256(canonical.encode()).hexdigest()[:20],
            "issuer":issuer,
            "vendor_gap_diagnosis":task["vendor_gap_diagnosis"],
            "vendor_original_csv_sha256":sha,
            "review_action":task["research_action"],
            "original_pdf_text_leads":len(docs),
            "original_resume_text_pairs":len(pairs),
            "original_pdf_sha_locators":"; ".join(locators),
            "missing_independent_official_proofs":"; ".join(needs),
            "review_status":"NOT_AUTHENTICATED",
            "historical_PIT_verified":False,
            "buy_eligible":False,
        })
    if set(by_issuer) != seen:
        raise ValueError("P3 issuer source coverage mismatch")
    rows.sort(key=lambda r:r["issuer"])
    return {"phase":"P3_MANUAL_OFFICIAL_EVIDENCE_CHECKLIST",
            "source_epoch_sha256":epoch,
            "p2_source_run_id":queue["p2_source_run_id"],
            "p3_source_run_id":queue["p3_source_run_id"],
            "review_count":len(rows),
            "asof_nontradable_tasks":sum(r["vendor_gap_diagnosis"]==ASOF_GAP for r in rows),
            "review_rows":rows,
            "official_first_publication_authenticated":0,
            "official_state_intervals_certified":0,
            "feature_gaps_resolved":0,
            "historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--queue",required=True,type=Path)
    p.add_argument("--provenance",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--csv",required=True,type=Path)
    a=p.parse_args()
    result=export(json.loads(a.queue.read_text()),json.loads(a.provenance.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.csv.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    fields=list(result["review_rows"][0])
    with a.csv.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(result["review_rows"])
    print(json.dumps({"review_count":result["review_count"],
        "asof_nontradable_tasks":result["asof_nontradable_tasks"],
        "official_state_intervals_certified":0,"trade_gate":"BLOCKED"}))

if __name__=="__main__":
    main()
