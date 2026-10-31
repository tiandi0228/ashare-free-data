import hashlib,json,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from collector.baostock_batch import FIELDS,END
from collector.p4_real_archive_preflight import COHORT,inspect

class LiveArchivePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"5ba00fbd720fad90"
        self.shard=self.root/"shard_0098"
        self.shard.mkdir(parents=True)
        self.epoch="5ba00fbd720fad90"+"a"*48
        self.source_status={"source_sha256":self.epoch,
                            "trade_gate":"BLOCKED","archived_shards":[98]}
        self.write_status()
        ds=[]
        d=date.fromisoformat(END)
        while len(ds)<25:
            if d.weekday()<5:ds.append(d.isoformat())
            d-=timedelta(days=1)
        self.dates=sorted(ds)
        self.receipt={"status":"OBSERVED_SUBSET_UNVERIFIED",
            "historical_point_in_time_universe_verified":False,
            "trade_gate":"BLOCKED","orders":[],"issuer_count":8,"results":[]}
        for code in COHORT:
            self.add_code(code,self.dates)
        self.write_receipt()
    def write_status(self):
        (self.root/"archive_status.json").write_text(json.dumps(self.source_status))
    def write_receipt(self):
        (self.shard/"quality.json").write_text(json.dumps(self.receipt))
    def add_code(self,code,dates):
        fields=",".join(FIELDS)+"\n"
        for d in dates:
            fields+=f"{d},{code},10,11,9,10,100,1000,3,1\n"
        raw=fields.encode()
        (self.shard/(code.replace(".","_")+".csv")).write_bytes(raw)
        self.receipt["results"]=[r for r in self.receipt["results"] if r["code"]!=code]
        self.receipt["results"].append({"code":code,"status":"OBSERVED_UNVERIFIED",
            "rows":len(dates),"tradable_rows":len(dates),"suspended_status_rows":0,
            "sha256":hashlib.sha256(raw).hexdigest()})
    def test_verified_actual_eight_source_originals(self):
        report=inspect(self.root,"c"*40)
        self.assertEqual(report["status"],
                         "EIGHT_SOURCE_ORIGINALS_INDEPENDENTLY_VERIFIED")
        self.assertEqual(report["verified_issuers"],8)
        self.assertEqual({r["code"] for r in report["source_details"]},set(COHORT))
        self.assertEqual({r["frozen_end"] for r in report["source_details"]},{END})
        self.assertEqual(report["source_archive_commit"],"c"*40)
        self.assertTrue(report["ready_for_bounded_vendor_research_attempt"])
        self.assertFalse(report["historical_PIT_verified"])
        self.assertFalse(report["complete_mainboard_coverage"])
        self.assertEqual(report["strategy_buy_signals_authorized"],0)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        self.assertEqual(report["orders"],[])
    def test_archive_status_must_explicitly_include_source_shard(self):
        self.source_status["archived_shards"]=[99]
        self.write_status()
        with self.assertRaisesRegex(ValueError,"pilot shard status"):
            inspect(self.root)
    def test_tampered_vendor_csv_fails_independent_sha_replay(self):
        target=self.shard/"sh_601100.csv"
        target.write_bytes(target.read_bytes()+b"tampered")
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            inspect(self.root)
    def test_truncated_history_after_archive_fails_original_bar_window(self):
        self.add_code(COHORT[0],self.dates[:18]);self.write_receipt()
        with self.assertRaisesRegex(ValueError,"insufficient MA20 closes"):
            inspect(self.root)
    def test_modified_original_last_date_never_treated_as_ready(self):
        self.add_code(COHORT[1],self.dates[:-1]);self.write_receipt()
        with self.assertRaisesRegex(ValueError,"anchor missing"):
            inspect(self.root)
    def test_bad_archive_epoch_and_trading_gate_rejected(self):
        self.source_status["source_sha256"]="b"*64
        self.write_status()
        with self.assertRaisesRegex(ValueError,"pilot shard status"):
            inspect(self.root)
        self.source_status["source_sha256"]=self.epoch
        self.source_status["trade_gate"]="OPEN"
        self.write_status()
        with self.assertRaisesRegex(ValueError,"pilot shard status"):
            inspect(self.root)
    def test_extra_false_issuer_is_not_accepted_into_fixed_research_sample(self):
        self.receipt["results"][0]["code"]="sh.600000"
        self.write_receipt()
        with self.assertRaises(ValueError):
            inspect(self.root)
    def test_read_only_workflow_preflight_runs_before_vendor_fetch(self):
        wf=(Path(__file__).resolve().parents[1]/
            ".github/workflows/p4-current-tail-ma20-pilot.yml").read_text()
        self.assertIn("tests.test_p4_real_archive_preflight",wf)
        self.assertIn("collector.p4_real_archive_preflight",wf)
        self.assertLess(wf.index("Independent frozen-source preflight before provider access"),
                        wf.index("Install only the free market-data SDK"))
        self.assertIn("permissions:\n  contents: read",wf)
        self.assertIn("trade_gate",inspect(self.root))

if __name__=="__main__":unittest.main()
