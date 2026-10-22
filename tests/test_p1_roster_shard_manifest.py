import tempfile, unittest
from pathlib import Path
from collector.p1_roster_shard_manifest import select_roster
from collector.baostock_batch import manifest, CAP

class RosterShardTests(unittest.TestCase):
    def test_deterministic_128_manifest_and_sixteen_shards(self):
        rows=[{"code":f"sh.600{i:03d}"} for i in range(150)]
        rows.extend([{"code":"sz.300001"},{"code":"sh.688001"}])
        content,report=select_roster(list(reversed(rows)))
        self.assertEqual(report["selected_count"],128)
        self.assertEqual(report["candidate_mainboard_count"],150)
        self.assertFalse(report["historical_asof_verified"])
        self.assertEqual(report["trade_gate"],"BLOCKED")
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"m.txt";path.write_text(content)
            codes,sha=manifest(path)
            self.assertEqual(len(codes),128)
            self.assertEqual((len(codes)+CAP-1)//CAP,16)
            self.assertEqual(sha,report["manifest_sha256"])
    def test_all_available_mainboard_prefix_strata_are_sampled(self):
        prefixes=("sh.600","sh.601","sh.603","sh.605","sz.000","sz.001","sz.002","sz.003")
        rows=[{"code":f"{prefix}{i:03d}"} for prefix in prefixes for i in range(40)]
        content,receipt=select_roster(rows)
        self.assertEqual(len(content.splitlines()),128)
        self.assertEqual(receipt["prefix_counts"],{prefix:16 for prefix in prefixes})
        self.assertEqual(receipt["candidate_mainboard_count"],320)
        self.assertEqual(select_roster(list(reversed(rows)))[0],content)
        self.assertFalse(receipt["historical_asof_verified"])
    def test_duplicate_code_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            select_roster([{"code":"sh.600001"},{"code":"sh.600001"}])
    def test_invalid_and_empty_fail_closed(self):
        with self.assertRaises(ValueError):select_roster([{"code":"sz.300001"}])
        with self.assertRaises(ValueError):select_roster([{"code":"sh.600001"}],maximum=129)
if __name__=="__main__":unittest.main()
