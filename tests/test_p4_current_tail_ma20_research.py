import csv,hashlib,json,tempfile,unittest
from datetime import date,datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo
from collector.baostock_batch import FIELDS
from collector.p4_current_tail_ma20_research import run,verify,safe_day,crossings

class Query:
    def __init__(self,rows):
        self.fields=FIELDS
        self.error_code="0"
        self.rows=rows
    def next(self):
        if not self.rows:return False
        self._current=self.rows.pop(0)
        return True
    def get_row_data(self):return self._current

class Vendor:
    def __init__(self,rows):
        self.rows=rows
        self.calls=[]
        self.logouts=0
    def login(self):return SimpleNamespace(error_code="0")
    def logout(self):self.logouts+=1
    def query_history_k_data_plus(self,code,**kw):
        self.calls.append((code,kw))
        return Query([list(x) for x in self.rows])

def row(day,price):
    px=str(price)
    return [day,"sh.600000",px,px,px,px,"1000","10000","3","1"]

class CurrentTailTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.archive=self.root/"archive"/"5ba00fbd720fad90"
        self.arc=self.archive/"shard_0000"
        self.arc.mkdir(parents=True)
        (self.archive/"archive_status.json").write_text(json.dumps({
            "source_sha256":"5ba00fbd720fad90"+"a"*48,"trade_gate":"BLOCKED"}))
        self.out=self.root/"out"
        dates=[]
        d=date(2026,10,20)
        while len(dates)<25:
            if d.weekday()<5:dates.append(d.isoformat())
            d-=timedelta(days=1)
        dates=sorted(dates)
        self.base=[row(day,9 if i==24 else 10) for i,day in enumerate(dates)]
        self.tail=[self.base[-1],row("2026-10-21",12),row("2026-10-22",12),
                   row("2026-10-23",8),row("2026-10-26",13)]
        self.arc.joinpath("sh_600000.csv").write_text(
            ",".join(FIELDS)+"\n"+"".join(",".join(r)+"\n" for r in self.base))
        self.arc.joinpath("quality.json").write_text("{}")
        self.now=datetime(2026,10,31,9,55,tzinfo=ZoneInfo("Asia/Shanghai"))
        self.vendor=Vendor(self.tail)
        self.patcher=patch("collector.p4_current_tail_ma20_research.assess",
                           return_value={"details":[{"code":"sh.600000"}]})
        self.patcher.start();self.addCleanup(self.patcher.stop)
    def capture(self):
        return run(self.archive,self.out,self.vendor,
                   as_of="2026-10-30",now=self.now,
                   archive_commit="a"*40)
    def test_crossing_independently_replayed_without_buy(self):
        manifest=self.capture()
        self.assertEqual(manifest["status"],"OBSERVED_BOUNDED_RESEARCH")
        self.assertEqual([x["completed_close_day"] for x in
            manifest["non_executable_ma20_crossing_events"]],
            ["2026-10-21","2026-10-26"])
        self.assertEqual(manifest["new_source_rows"],4)
        self.assertEqual(manifest["captured_issuer_count"],1)
        self.assertEqual(manifest["strategy_buy_signals_certified"],0)
        self.assertEqual(manifest["trade_gate"],"BLOCKED")
        self.assertEqual(manifest["orders"],[])
        self.assertEqual(manifest["executable_candidates"],[])
        result=verify(self.archive,self.out)
        self.assertEqual(result["verified_non_executable_crossings"],2)
        self.assertEqual(result["new_rows_verified"],4)
        self.assertFalse(result["complete_mainboard_coverage"])
        self.assertEqual(len(self.vendor.calls),1)
        self.assertEqual(self.vendor.calls[0][1]["start_date"],"2026-10-20")
        self.assertEqual(self.vendor.calls[0][1]["end_date"],"2026-10-30")
        self.assertEqual(self.vendor.logouts,1)
    def test_missing_event_even_if_claimed_counts_adjusted_rejected(self):
        manifest=self.capture()
        manifest["non_executable_ma20_crossing_events"].pop(0)
        (self.out/"current_tail_report.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,"incomplete or altered"):
            verify(self.archive,self.out)
    def test_altered_source_bytes_even_with_report_not_edited_rejected(self):
        self.capture()
        f=self.out/"sh_600000_current.csv"
        f.write_bytes(f.read_bytes().replace(b"2026-10-26",b"2026-10-27"))
        with self.assertRaisesRegex(ValueError,"source hash"):
            verify(self.archive,self.out)
    def test_conflicting_source_anchor_cannot_create_signal(self):
        self.vendor.rows[0][5]="99"
        report=self.capture()
        self.assertEqual(report["status"],"BLOCKED_PARTIAL")
        self.assertEqual(report["captured_issuer_count"],0)
        self.assertEqual(report["non_executable_ma20_crossing_events"],[])
        with self.assertRaisesRegex(ValueError,"unsafe or incomplete"):
            verify(self.archive,self.out)
    def test_unfinished_asof_and_unsafe_clock_rejected(self):
        for day in ("2026-11-02","2026-10-20"):
            with self.subTest(day=day):
                with self.assertRaisesRegex(ValueError,"as-of"):
                    run(self.archive,self.out,self.vendor,
                        as_of=day,now=self.now)
        with self.assertRaisesRegex(ValueError,"naive"):
            safe_day(datetime(2026,10,30,20))
    def test_no_archive_is_not_claimed_as_zero_signals(self):
        with self.assertRaisesRegex(ValueError,"no archived"):
            run(self.root/"empty",self.out,self.vendor,as_of="2026-10-30",
                now=self.now)
    def test_90day_rebase_prevents_stale_history_pilot(self):
        later=datetime(2027,2,5,19,tzinfo=ZoneInfo("Asia/Shanghai"))
        with self.assertRaisesRegex(ValueError,"rebase required"):
            run(self.archive,self.out,self.vendor,
                as_of="2027-02-05",now=later)
    def test_cross_epoch_mixing_and_forged_provenance_rejected(self):
        self.capture()
        report_path=self.out/"current_tail_report.json"
        report=json.loads(report_path.read_text())
        report["source_epoch_sha256"]="b"*64
        report_path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,"source epoch changed"):
            verify(self.archive,self.out)
        self.archive.joinpath("archive_status.json").write_text(json.dumps({
            "source_sha256":"b"*64,"trade_gate":"BLOCKED"}))
        with self.assertRaisesRegex(ValueError,"archive epoch provenance"):
            run(self.archive,self.out,self.vendor,as_of="2026-10-30",now=self.now)

    def test_suspended_row_breaks_crossing_continuity(self):
        prior=[dict(zip(FIELDS,r)) for r in self.base]
        future=[dict(zip(FIELDS,r)) for r in self.tail[1:]]
        self.assertEqual(crossings(prior,future,"2026-10-20"),
                         ["2026-10-21","2026-10-26"])
        future[0]["tradestatus"]="0"
        self.assertNotIn("2026-10-21",
                         crossings(prior,future,"2026-10-20"))

if __name__=="__main__":unittest.main()
