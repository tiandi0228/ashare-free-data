import csv,hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p1_fresh_shard_plan import plan

class ShardPlanTests(unittest.TestCase):
    def test_complete_unique_eight_shards(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"source.csv"
            with source.open("w",newline="") as f:
                w=csv.writer(f);w.writerow(("code","tradeStatus","code_name"))
                for i in range(1001):w.writerow((f"sh.{600000+i}","1",f"issuer{i}"))
            r=plan(source,Path(d)/"out","2026-10-22")
            self.assertEqual(r["issuer_count"],1001)
            self.assertEqual(r["shard_count"],126)
            self.assertEqual(r["shards"][-1]["count"],1)
            self.assertEqual(r["trade_gate"],"BLOCKED")
            self.assertFalse(r["historical_PIT_verified"])
            for s in r["shards"]:
                b=(Path(d)/"out"/s["name"]).read_bytes()
                self.assertEqual(hashlib.sha256(b).hexdigest(),s["sha256"])
    def test_duplicates_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"source.csv"
            source.write_text("code,tradeStatus,code_name\n"+("sh.600000,1,name\n"*1000))
            with self.assertRaises(ValueError):
                plan(source,Path(d)/"out","2026-10-22")
if __name__=="__main__":unittest.main()
