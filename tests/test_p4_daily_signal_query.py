import csv,json,tempfile,unittest
from datetime import date,datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
from collector.baostock_batch import FIELDS
from collector.p4_current_tail_ma20_research import run
from collector.p4_current_tail_permanent_archive import prepare,stage
from collector.p4_daily_signal_query import query

class Vendor:
    def __init__(self,rows):self.rows=rows
    def login(self):return SimpleNamespace(error_code="0")
    def logout(self):pass
    def query_history_k_data_plus(self,code,**kwargs):
        class Q:
            fields=FIELDS
            error_code="0"
            def __init__(self,rows):self.items=list(rows)
            def next(self):
                if not self.items:return False
                self.current=self.items.pop(0)
                return True
            def get_row_data(self):return self.current
        return Q(self.rows)

def bar(day,price):
    px=str(price)
    return [day,"sh.600000",px,px,px,px,"100","1000","3","1"]

class DailySignalQueryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.archive=self.root/"perm"
        self.epoch=self.root/"original"/"5ba00fbd720fad90"
        folder=self.epoch/"shard_0000";folder.mkdir(parents=True)
        self.commit="a"*40
        (self.epoch/"archive_status.json").write_text(json.dumps({
            "source_sha256":"5ba00fbd720fad90"+"a"*48,"trade_gate":"BLOCKED"}))
        ds=[];d=date(2026,10,20)
        while len(ds)<25:
            if d.weekday()<5:ds.append(d.isoformat())
            d-=timedelta(days=1)
        history=[bar(day,9 if i==24 else 10) for i,day in enumerate(sorted(ds))]
        (folder/"sh_600000.csv").write_text(
            ",".join(FIELDS)+"\n"+"".join(",".join(row)+"\n" for row in history))
        (folder/"quality.json").write_text("{}")
        self.now=datetime(2026,10,31,12,tzinfo=ZoneInfo("Asia/Shanghai"))
        self.rows=[history[-1],bar("2026-10-21",12),bar("2026-10-22",12),
                   bar("2026-10-23",8),bar("2026-10-26",13),
                   bar("2026-10-27",13),bar("2026-10-28",13),
                   bar("2026-10-29",13),bar("2026-10-30",13)]
        p=patch("collector.p4_current_tail_ma20_research.assess",
                return_value={"details":[{"code":"sh.600000"}]})
        p.start();self.addCleanup(p.stop)
    def add_snapshot(self,run_id,rows=None):
        capture=self.root/("capture_"+str(run_id))
        record=run(self.epoch,capture,Vendor(rows if rows is not None else self.rows),
                   as_of="2026-10-30",now=self.now,archive_commit=self.commit)
        self.assertEqual(record["status"],"OBSERVED_BOUNDED_RESEARCH")
        path,files,_=prepare(self.epoch,capture,run_id,1,self.commit)
        stage(self.archive,path,files)
        return self.archive/path
    def test_no_archives_is_missing_not_zero_signals(self):
        result=query(self.archive,self.epoch,"2026-10-26","2026-10-30")
        self.assertEqual(result["verified_archive_runs"],0)
        self.assertEqual(result["observed_non_executable_crossings"],[])
        self.assertTrue(all(d["status"]=="NO_VERIFIED_VENDOR_ROWS_FOR_DAY"
                            and d["observed_non_executable_crossing_count"] is None
                            for d in result["days"]))
        self.assertFalse(result["full_market_scan_performed"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_exact_day_from_permanent_replay_not_actionable(self):
        self.add_snapshot(100)
        result=query(self.archive,self.epoch,"2026-10-26")
        day=result["days"][0]
        self.assertEqual(day["status"],"VERIFIED_BOUNDED_PILOT_DAY")
        self.assertEqual(day["observed_issuer_count"],1)
        self.assertEqual(day["observed_non_executable_crossing_count"],1)
        self.assertEqual(day["codes_with_crossing"],["sh.600000"])
        self.assertEqual(result["observed_non_executable_crossings"],
            [{"code":"sh.600000","completed_close_day":"2026-10-26",
              "signal_known_after_close_only":True,"entry_filled":False}])
        self.assertEqual(result["strategy_buy_signals_authorized"],0)
        self.assertEqual(result["orders"],[])
    def test_complete_pilot_day_with_no_crossing_is_zero_only_for_sample(self):
        self.add_snapshot(100)
        report=query(self.archive,self.epoch,"2026-10-30")
        self.assertEqual(report["days"][0]["observed_non_executable_crossing_count"],0)
        self.assertEqual(report["days"][0]["status"],"VERIFIED_BOUNDED_PILOT_DAY")
        self.assertFalse(report["complete_mainboard_coverage"])
    def test_weekend_is_unknown_not_false_zero(self):
        self.add_snapshot(100)
        report=query(self.archive,self.epoch,"2026-10-30","2026-10-31")
        self.assertEqual(report["days"][0]["observed_non_executable_crossing_count"],0)
        self.assertEqual(report["days"][1]["status"],"NO_VERIFIED_VENDOR_ROWS_FOR_DAY")
        self.assertIsNone(report["days"][1]["observed_non_executable_crossing_count"])
    def test_same_day_multiple_run_receipts_deduplicate_events(self):
        self.add_snapshot(100);self.add_snapshot(101)
        report=query(self.archive,self.epoch,"2026-10-21","2026-10-26")
        self.assertEqual(report["verified_archive_runs"],2)
        self.assertEqual(len(report["observed_non_executable_crossings"]),2)
        self.assertEqual([e["completed_close_day"]
                          for e in report["observed_non_executable_crossings"]],
                         ["2026-10-21","2026-10-26"])
    def test_conflicting_rows_between_runs_are_not_arbitrarily_chosen(self):
        self.add_snapshot(100)
        altered=[list(r) for r in self.rows]
        altered[4]=bar("2026-10-26",14)
        self.add_snapshot(101,altered)
        with self.assertRaisesRegex(ValueError,"conflicting immutable vendor evidence"):
            query(self.archive,self.epoch,"2026-10-26")
    def test_tampered_permanent_csv_blocks_entire_day_report(self):
        target=self.add_snapshot(100)
        f=target/"sh_600000_current.csv"
        f.write_bytes(f.read_bytes().replace(b"2026-10-26",b"2026-10-27"))
        with self.assertRaises(ValueError):
            query(self.archive,self.epoch,"2026-10-26")
    def test_bad_provenance_rejected_not_ignored(self):
        target=self.add_snapshot(100)
        f=target/"permanent_receipt.json"
        data=json.loads(f.read_text());data["github_run_id"]=333
        f.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,"provenance mismatch"):
            query(self.archive,self.epoch,"2026-10-26")
    def test_invalid_day_ranges_never_claim_coverage(self):
        for start,end in [("2026-10-20","2026-10-21"),
                          ("2026-10-30","2026-10-26"),
                          ("2026-10-21","2026-11-30")]:
            with self.subTest(start=start,end=end):
                with self.assertRaisesRegex(ValueError,"1 to 31 days"):
                    query(self.archive,self.epoch,start,end)
    def test_unexpected_archive_dir_rejected(self):
        self.archive.joinpath("p4-current-tail","5ba00fbd720fad90","bad_object").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,"unexpected archived"):
            query(self.archive,self.epoch,"2026-10-26")

if __name__=="__main__":unittest.main()
