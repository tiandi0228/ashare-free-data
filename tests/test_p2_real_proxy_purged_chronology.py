import copy,unittest
from collector.p2_real_proxy_purged_chronology import observe,PHASE,PAGE

def row(i,day,next_day,last_day):
    return {"issuer":"sh.600"+str(i).zfill(3),"original_csv_sha256":"b"*64,
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
    def test_duplicate_ids_and_unbounded_pages_refused(self):
        a=row(1,"2026-05-21","2026-05-22","2026-05-26")
        q=observe(proxy([a,a]),"2026-06-30","2026-07-08","2026-10-22")
        self.assertEqual(q["status"],"REJECTED")
        q=observe(proxy([a]),"2026-06-30","2026-07-08","2026-10-22",page_index=1)
        self.assertEqual(q["status"],"REJECTED")

if __name__=="__main__":unittest.main()
