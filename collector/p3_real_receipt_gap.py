"""Turn a real prior 600421 two-PDF receipt into a P3 evidence gap audit.

This does not convert historical event references to authenticated as-of
observations. Provider source hashes without original bytes/timestamp cannot
satisfy official completeness.
"""
import argparse
import json
from pathlib import Path
from collector.p3_historical_evidence_coverage import audit_coverage

def reconcile(receipt):
    if (receipt.get("phase") != "P3_CNINFO_TWO_REAL_PDF_ISSUER_EVENT_CHAIN"
        or receipt.get("issuer") != "sh.600421"
        or receipt.get("first_capture_run_id") != 39580585146
        or receipt.get("second_capture_run_id") != 39579302851
        or receipt.get("source_sha256") != [
            "ef9b9113b2a51ca718e786de0613860351f0c8056916e7decb5a010da7acaff8",
            "6e43f458ee70b11dc5ab7331c2d67dee62dc26fa2121e138a2c93ef71c65409f",
        ] or receipt.get("asof_timestamp_authenticated") is not False
        or receipt.get("exchange_deletion_effective_original_obtained") is not False
        or receipt.get("original_pdf_bytes_recoverable_from_this_receipt") is not False
        or receipt.get("trade_gate") != "BLOCKED"):
        raise ValueError("unrecognized original two-PDF research evidence")
    expected_events = [
        {"type":"ISSUER_STATED_RESUMPTION_DATE","source_url_date":"2026-05-23","stated_date":"2026-06-01","actual_exchange_tradability_verified":False},
        {"type":"ISSUER_FORECAST_FINAL_TRADING_DATE","source_url_date":"2026-06-19","forecast":"2026-06-22","is_effective_exchange_delist":False},
        {"type":"EXCHANGE_EFFECTIVE_DELIST_DATE_AUDIT_REFERENCE_ONLY","reference_effective_date":"2026-06-26","first_party_original_observed_in_runner":False,"exchange_original_sha256":None},
    ]
    expected_days = ["2026-05-22","2026-05-23","2026-05-29","2026-06-01","2026-06-19","2026-06-22","2026-06-26"]
    if (receipt.get("events") != expected_events
        or receipt.get("seven_asof_days") != expected_days
        or receipt.get("source_run_conclusion") != "success"
        or receipt.get("source_run_id") != 39581101776
        or receipt.get("formal_full_market_history_verified") is not False
        or receipt.get("orders") != []
        or receipt.get("executable_candidates") != []):
        raise ValueError("historical event chronology or source scope altered")
    days=receipt.get("seven_asof_days")
    if not isinstance(days,list) or len(days)!=7:
        raise ValueError("frozen decision-day scope changed")
    report=audit_coverage(["sh.600421"],days,[])
    report.update({
        "status":"REAL_TWO_PDF_RECEIPT_PRESENT_OFFICIAL_HISTORY_UNVERIFIED",
        "source_capture_run_ids":[39580585146,39579302851],
        "source_receipt_sha256":receipt["source_sha256"],
        "issuer_documents_observed":2,
        "authenticated_official_state_records":0,
        "source_document_bytes_replayable":False,
        "historical_publication_instant_authenticated":False,
        "exchange_effective_delisting_original_obtained":False,
        "full_market_history_verified":False,
        "scope_is_full_mainboard":False,
        "trade_gate":"BLOCKED",
        "orders":[],
        "executable_candidates":[],
    })
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",default="reports/p3_600421_two_pdf_event_chain_20261021.json")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    report=reconcile(json.loads(Path(args.receipt).read_text(encoding="utf-8")))
    target=Path(args.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"missing":report["missing_evidence_cells"],"total":report["required_evidence_cells"]}))

if __name__=="__main__":
    main()
