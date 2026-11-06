"""Bounded P2 time-leakage research on already SHA-checked P4 vendor events.

The event dates and original CSV SHA originated in P4's independently replayed
archived OHLC research. This adapter tests chronology only; it MUST NOT turn
observed future prices into a signal, strategy return or certified OOS result.
"""
import argparse,hashlib,json,re
from pathlib import Path
from collector.p2_purged_oos_partition import partition

PHASE="P2_REAL_ARCHIVED_PROXY_PURGED_CHRONOLOGY_RESEARCH"
COMMIT=re.compile(r"[0-9a-f]{40}\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
MAX_ROWS=50000
PAGE=2000

def observe(proxy, train_end, validation_start, validation_end, *, page_index=0):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "historical_PIT_verified":False,"historical_OOS_validated":False,
          "strategy_returns_computed":False,"full_universe_verified":False,
          "strategy_alpha_validated":False}
    def fail(reason):return dict(base,reason=reason)
    if (not isinstance(proxy,dict) or
        proxy.get("phase")!="P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES" or
        proxy.get("status")!="OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST" or
        proxy.get("trade_gate")!="BLOCKED" or proxy.get("orders")!=[] or
        proxy.get("executable_candidates")!=[] or
        proxy.get("actionable_buy_signals")!=[] or
        proxy.get("historical_PIT_verified") is not False or
        proxy.get("historical_OOS_validated") is not False or
        proxy.get("strategy_backtest_certified") is not False or
        proxy.get("fills_assumed")!=0 or proxy.get("trades_assumed")!=0 or
        not isinstance(proxy.get("archive_commit_sha"),str) or
        not COMMIT.fullmatch(proxy["archive_commit_sha"])):
        return fail("UNSAFE_OR_UNPINNED_ARCHIVED_OBSERVATION")
    records=proxy.get("observed_price_pairs")
    count=proxy.get("observed_next_open_to_third_close")
    if (not isinstance(records,list) or type(count) is not int or
        not 1<=count<=MAX_ROWS or len(records)!=count or
        type(page_index) is not int or page_index<0 or page_index*PAGE>=count):
        return fail("TRUNCATED_SOURCE_OR_INVALID_PAGE")
    chosen=records[page_index*PAGE:(page_index+1)*PAGE]
    events=[]
    ids=set()
    for row in chosen:
        if not isinstance(row,dict):
            return fail("MALFORMED_ORIGINAL_EVENT")
        code,sha,day,next_day,last_day=(
            row.get("issuer"),row.get("original_csv_sha256"),
            row.get("signal_known_after_close_date"),
            row.get("next_vendor_date"),row.get("third_vendor_date"))
        if (not isinstance(code,str) or not re.fullmatch(
             r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",code) or
            not isinstance(sha,str) or not SHA.fullmatch(sha) or
            row.get("next_open_fill_assumed") is not False or
            row.get("exit_close_fill_assumed") is not False or
            row.get("trade_return") is not None or
            row.get("T_plus_1_execution_verified") is not False):
            return fail("FORGED_EXECUTION_OR_MISSING_SOURCE_SHA")
        key=code+"|"+day if isinstance(day,str) else None
        if key is None or key in ids:
            return fail("DUPLICATE_OR_MISSING_EVENT_ID")
        ids.add(key)
        events.append({"id":key,"source":"ARCHIVED_VENDOR_RESEARCH_UNVERIFIED",
                       "feature_asof":day,"label_start":next_day,
                       "label_end":last_day})
    folds=partition(events,train_end,validation_start,validation_end,5)
    if folds["status"]=="REJECTED":
        # Empty single pages are valid for a time-sequential archive; never
        # pretend that these missing folds form a complete validation split.
        if folds.get("reason")!="TRAIN_OR_HOLDOUT_EMPTY":
            return fail("CHRONOLOGY_REJECTED_"+folds.get("reason","UNKNOWN"))
        return dict(base,status="PAGE_MISSING_TRAIN_OR_HOLDOUT_NOT_CERTIFIED",
                    archive_commit_sha=proxy["archive_commit_sha"],
                    observed_total_event_count=count,page_index=page_index,
                    selected_source_events=len(events),page_size=PAGE,
                    source_event_ids=[x["id"] for x in events],
                    fold_empty=True,missing_full_page_evidence=True)
    return dict(base,status="ARCHIVED_VENDOR_CHRONOLOGY_PAGE_PURGED_NOT_OOS_VALIDATION",
                archive_commit_sha=proxy["archive_commit_sha"],
                observed_total_event_count=count,page_index=page_index,
                selected_source_events=len(events),page_size=PAGE,
                checked_training_events=folds["train_count"],
                checked_holdout_events=folds["holdout_count"],
                purged_or_censored_events=folds["purged_count"],
                source_event_ids=[x["id"] for x in events],
                fold_report=folds,missing_full_page_evidence=True,
                training_parameters_frozen_before_holdout_verified=False,
                point_in_time_universe_verified=False)

def audit_all_pages(proxy, train_end, validation_start, validation_end):
    """Account for every archive event exactly once, without inferring OOS.

    Each page replays independent input validation through observe(). Pages
    lacking one fold are reported separately, NEVER silently counted as
    completed validation. No single-page receipt can claim total coverage.
    """
    base={"phase":"P2_ARCHIVED_CHRONOLOGY_ALL_PAGES_ACCOUNTING",
          "status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],"actionable_buy_signals":[],
          "historical_PIT_verified":False,"historical_OOS_validated":False,
          "strategy_returns_computed":False,"strategy_parameters_frozen":False,
          "source_epoch_pit_certified":False}
    def fail(reason):return dict(base,reason=reason)
    if not isinstance(proxy,dict):
        return fail("INVALID_SOURCE_REPORT")
    count=proxy.get("observed_next_open_to_third_close")
    if type(count) is not int or not 1<=count<=MAX_ROWS:
        return fail("INVALID_OBSERVED_COUNT")
    expected_pages=(count+PAGE-1)//PAGE
    seen=set()
    train=holdout=purged=unclassified=0
    missing_folds=[]
    fingerprints=hashlib.sha256()
    for index in range(expected_pages):
        report=observe(proxy,train_end,validation_start,validation_end,
                       page_index=index)
        if report["status"] not in (
                "ARCHIVED_VENDOR_CHRONOLOGY_PAGE_PURGED_NOT_OOS_VALIDATION",
                "PAGE_MISSING_TRAIN_OR_HOLDOUT_NOT_CERTIFIED"):
            return fail("PAGE_"+str(index)+"_"+report.get("reason","REJECTED"))
        if (report.get("page_index")!=index or
            report.get("selected_source_events")!=len(report.get("source_event_ids",[])) or
            report.get("observed_total_event_count")!=count or
            report.get("archive_commit_sha")!=proxy.get("archive_commit_sha")):
            return fail("PAGE_ACCOUNTING_MISMATCH")
        identifiers=report["source_event_ids"]
        if any(v in seen for v in identifiers):
            return fail("DUPLICATED_EVENT_ACROSS_PAGES")
        seen.update(identifiers)
        for identifier in identifiers:
            fingerprints.update(identifier.encode("utf-8"))
            fingerprints.update(b"\\n")
        if report["status"]=="PAGE_MISSING_TRAIN_OR_HOLDOUT_NOT_CERTIFIED":
            unclassified+=len(identifiers)
            missing_folds.append(index)
        else:
            train+=report["checked_training_events"]
            holdout+=report["checked_holdout_events"]
            purged+=report["purged_or_censored_events"]
            if (train+holdout+purged+unclassified)>count:
                return fail("PAGE_COUNT_OVERFLOW")
    if len(seen)!=count or train+holdout+purged+unclassified!=count:
        return fail("INCOMPLETE_FULL_EVENT_ACCOUNTING")
    return dict(base,status="ALL_SOURCE_PAGES_ACCOUNTED_NOT_OOS_CERTIFICATION",
                archive_commit_sha=proxy["archive_commit_sha"],
                source_observations=count,
                audited_page_count=expected_pages,page_size=PAGE,
                unique_source_event_count=len(seen),
                ordered_source_event_ids_sha256=fingerprints.hexdigest(),
                page_complete_fold_train_events=train,
                page_complete_fold_holdout_events=holdout,
                page_complete_fold_purged_events=purged,
                incomplete_fold_page_indexes=missing_folds,
                incomplete_fold_page_event_count=unclassified,
                all_pages_accounted=True,
                full_page_validation_coverage_certified=False,
                training_params_pre_holdout_authenticated=False,
                historical_exchange_calendar_authenticated=False)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--proxy",required=True)
    p.add_argument("--train-end",default="2026-06-30")
    p.add_argument("--validation-start",default="2026-07-08")
    p.add_argument("--validation-end",default="2026-10-22")
    p.add_argument("--page-index",type=int,default=0)
    p.add_argument("--all-pages",action="store_true")
    p.add_argument("--out",required=True)
    args=p.parse_args()
    proxy=json.loads(Path(args.proxy).read_text())
    if args.all_pages:
        result=audit_all_pages(proxy,args.train_end,args.validation_start,
                               args.validation_end)
    else:
        result=observe(proxy,args.train_end,args.validation_start,
                       args.validation_end,page_index=args.page_index)
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result.get(k) for k in (
        "status","observed_total_event_count","selected_source_events",
        "checked_training_events","checked_holdout_events",
        "purged_or_censored_events","audited_page_count","unique_source_event_count",
        "incomplete_fold_page_event_count","trade_gate")}))
    if result["status"]=="REJECTED":raise SystemExit(1)
if __name__=="__main__":main()
