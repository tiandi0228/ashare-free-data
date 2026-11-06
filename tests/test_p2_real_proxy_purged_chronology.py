import copy,unittest
from collector.p2_real_proxy_purged_chronology import observe,audit_all_pages,PHASE,PAGE

def row(i,day,next_day,last_day):
    return {"issuer":"sh."+str(600000+i),"original_csv_sha256":"b"*64,
            "signal_known_after_close_date":day,
            "next_vendor_date":next_day,"third_vendor_date":last_day,
            "next_open_fill_assumed":False,"exit_close_fill_assumed":False,
            "trade_return":None,"T_plus_1_execution_verified":False}
def proxy(rows):
    return {"phase":"P4_NEXT_OPEN_FORWARD_PRICE_PROXY_NOT_TRADES",
            "status":"OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST",
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "actionable_buy_signals":[],"historical_PIT_verified":False,
            "historical_OOS_validated":False,"strategy_backtest_certified":False,
            "fills_assumed":0,"trades_assumed":0,
            "archive_commit_sha":"a"*40,
            "observed_next_open_to_third_close":len(rows),
            "observed_price_pairs":rows}
class RealProxyFoldTests(unittest.TestCase):
    def test_real_source_chronology_purges_crossing_labels_without_returns(self):
        rows=[
          row(1,"2026-05-21","2026-05-22","2026-05-26"),
          row(2,"2026-06-29","2026-06-30","2026-07-02"),
          row(3,"2026-07-09","2026-07-10","2026-07-14"),
          row(4,"2026-10-21","2026-10-22","2026-10-23"),
        ]
        q=observe(proxy(rows),"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(q["status"],"ARCHIVED_VENDOR_CHRONOLOGY_PAGE_PURGED_NOT_OOS_VALIDATION")
        self.assertEqual(q["checked_training_events"],1)
        self.assertEqual(q["checked_holdout_events"],1)
        self.assertEqual(q["purged_or_censored_events"],2)
        self.assertEqual(q["observed_total_event_count"],4)
        self.assertEqual(q["archive_commit_sha"],"a"*40)
        self.assertFalse(q["historical_OOS_validated"])
        self.assertFalse(q["training_parameters_frozen_before_holdout_verified"])
        self.assertFalse(q["strategy_returns_computed"])
        self.assertEqual(q["orders"],[])
        self.assertEqual(q["trade_gate"],"BLOCKED")
    def test_empty_fold_is_reported_never_certified(self):
        q=observe(proxy([row(1,"2026-05-21","2026-05-22","2026-05-26")]),
                  "2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(q["status"],"PAGE_MISSING_TRAIN_OR_HOLDOUT_NOT_CERTIFIED")
        self.assertTrue(q["fold_empty"])
        self.assertFalse(q["historical_OOS_validated"])
    def test_forged_source_and_future_fill_is_refused(self):
        initial=proxy([row(1,"2026-05-21","2026-05-22","2026-05-26"),
                       row(2,"2026-07-09","2026-07-10","2026-07-14")])
        changes=[
          lambda x:x.update(trade_gate="OPEN"),
          lambda x:x.update(archive_commit_sha="main"),
          lambda x:x.update(observed_next_open_to_third_close=3),
          lambda x:x["observed_price_pairs"][0].update(trade_return="0.1"),
          lambda x:x["observed_price_pairs"][0].update(next_open_fill_assumed=True),
          lambda x:x["observed_price_pairs"][0].update(original_csv_sha256="forged"),
          lambda x:x["observed_price_pairs"][0].update(issuer="sz.300001"),
          lambda x:x["observed_price_pairs"][1].update(next_vendor_date="2026-07-01"),
        ]
        for change in changes:
            with self.subTest(change=change):
                q=copy.deepcopy(initial);change(q)
                r=observe(q,"2026-06-30","2026-07-08","2026-10-22")
                self.assertEqual(r["status"],"REJECTED")
                self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_nonforward_labels_rejected_and_sha_binds_full_row(self):
        train=row(1,"2026-05-21","2026-05-22","2026-05-26")
        hold=row(2,"2026-07-09","2026-07-10","2026-07-14")
        base=proxy([train,hold])
        good=audit_all_pages(base,"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(good["status"],"ALL_SOURCE_PAGES_ACCOUNTED_NOT_OOS_CERTIFICATION")
        self.assertEqual(len(good["archived_label_windows_sha256"]),64)
        self.assertEqual(len(good["fold_configuration_sha256"]),64)
        self.assertFalse(good["historical_OOS_validated"])
        for key,value in [
            ("next_vendor_date","2026-05-21"),
            ("third_vendor_date","2026-05-22"),
            ("next_vendor_date","2026-05-20"),
            ("third_vendor_date","2026-05-21"),
        ]:
            with self.subTest(key=key,value=value):
                corrupt=copy.deepcopy(base)
                corrupt["observed_price_pairs"][0][key]=value
                q=audit_all_pages(corrupt,"2026-06-30","2026-07-08","2026-10-22")
                self.assertEqual(q["status"],"REJECTED")
                self.assertIn("NON_FORWARD",q["reason"])
                self.assertEqual(q["trade_gate"],"BLOCKED")
        changed=copy.deepcopy(base)
        changed["observed_price_pairs"][0]["original_csv_sha256"]="c"*64
        alternate=audit_all_pages(changed,"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(alternate["status"],good["status"])
        self.assertEqual(alternate["ordered_source_event_ids_sha256"],
                         good["ordered_source_event_ids_sha256"])
        self.assertNotEqual(alternate["archived_label_windows_sha256"],
                            good["archived_label_windows_sha256"])
        self.assertNotEqual(alternate["fold_configuration_sha256"],
                            good["fold_configuration_sha256"])
        changed=copy.deepcopy(base)
        changed["observed_price_pairs"][1]["third_vendor_date"]="2026-07-15"
        later=audit_all_pages(changed,"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(later["status"],good["status"])
        self.assertNotEqual(later["archived_label_windows_sha256"],
                            good["archived_label_windows_sha256"])
        self.assertEqual(later["trade_gate"],"BLOCKED")

    def test_duplicate_ids_and_unbounded_pages_refused(self):
        a=row(1,"2026-05-21","2026-05-22","2026-05-26")
        q=observe(proxy([a,a]),"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(q["status"],"REJECTED")
        q=observe(proxy([a]),"2026-06-30","2026-07-08","2026-10-22",page_index=1)
        self.assertEqual(q["status"],"REJECTED")

    def test_all_pages_accounted_without_false_fold_coverage(self):
        rows=[row(i,"2026-05-21","2026-05-22","2026-05-26")
              for i in range(PAGE+1)]
        # Ensure first page has both time folds, the final page is missing
        # a holdout fold and must not become a false successful OOS result.
        rows[1].update(signal_known_after_close_date="2026-07-09",
                       next_vendor_date="2026-07-10",
                       third_vendor_date="2026-07-14")
        q=audit_all_pages(proxy(rows),"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(q["status"],"ALL_SOURCE_PAGES_ACCOUNTED_NOT_OOS_CERTIFICATION")
        self.assertEqual(q["source_observations"],PAGE+1)
        self.assertEqual(q["unique_source_event_count"],PAGE+1)
        self.assertEqual(q["audited_page_count"],2)
        self.assertEqual(q["page_complete_fold_train_events"],PAGE-1)
        self.assertEqual(q["page_complete_fold_holdout_events"],1)
        self.assertEqual(q["incomplete_fold_page_event_count"],1)
        self.assertEqual(q["incomplete_fold_page_indexes"],[1])
        self.assertTrue(q["all_pages_accounted"])
        self.assertFalse(q["full_page_validation_coverage_certified"])
        self.assertFalse(q["historical_OOS_validated"])
        self.assertEqual(q["trade_gate"],"BLOCKED")

    def test_cross_page_duplicate_and_forged_overall_counts_rejected(self):
        rows=[row(i,"2026-05-21","2026-05-22","2026-05-26")
              for i in range(PAGE+1)]
        rows[-1]=dict(rows[0])
        q=audit_all_pages(proxy(rows),"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(q["status"],"REJECTED")
        self.assertEqual(q["reason"],"DUPLICATED_EVENT_ACROSS_PAGES")
        self.assertEqual(q["orders"],[])
        p=proxy(rows);p["observed_next_open_to_third_close"]-=1
        q=audit_all_pages(p,"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(q["status"],"REJECTED")
        self.assertEqual(q["trade_gate"],"BLOCKED")

if __name__=="__main__":unittest.main()
