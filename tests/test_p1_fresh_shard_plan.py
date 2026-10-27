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
    def test_membership_digest_is_stable_across_csv_metadata_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            rows=[(f"sh.{600000+i}","1",f"name{i}") for i in range(1000)]
            source=Path(d)/"a.csv"
            with source.open("w",newline="") as f:
                w=csv.writer(f);w.writerow(("code","tradeStatus","code_name"));w.writerows(rows)
            first=plan(source,Path(d)/"first","2026-10-22")
            other=Path(d)/"b.csv"
            with other.open("w",newline="") as f:
                w=csv.writer(f);w.writerow(("code","tradeStatus","code_name"))
                w.writerows((code,status,"renamed") for code,status,_ in reversed(rows))
            second=plan(other,Path(d)/"second","2026-10-23")
            self.assertNotEqual(first["source_sha256"],second["source_sha256"])
            self.assertEqual(first["roster_codes_sha256"],second["roster_codes_sha256"])
            self.assertEqual(first["shards"],second["shards"])

    def test_duplicates_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"source.csv"
            source.write_text("code,tradeStatus,code_name\n"+("sh.600000,1,name\n"*1000))
            with self.assertRaises(ValueError):
                plan(source,Path(d)/"out","2026-10-22")
if __name__=="__main__":unittest.main()
