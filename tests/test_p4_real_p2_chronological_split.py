import unittest
from datetime import date
from collector.p4_real_p2_chronological_split import audit
class SplitTests(unittest.TestCase):
    def test_repeated_original_identical_or_conflicting(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            raw="date,close,tradestatus\n2025-12-30,10,1\n2026-01-02,11,1\n2026-01-05,11,1\n2026-01-06,11,1\n2026-01-07,11,1\n2026-01-08,11,1\n2026-01-09,11,1\n"
            for i in (0,1):
                d=root/str(i)/"shard_0000"
                d.mkdir(parents=True)
                (d/"quality.json").write_text("{}")
                (d/"sh_600000.csv").write_text(raw)
            with patch("collector.p4_real_p2_chronological_split.assess",return_value={"details":[{"code":"sh.600000"}]}):
                result=audit(root,"2025-12-31")
                self.assertEqual(result["identical_duplicate_receipts_skipped"],1)
                self.assertEqual(result["verified_issuers"],1)
                self.assertEqual(result["issuers_with_5_holdout_rows"],1)
                self.assertEqual(result["issuers_with_5_vendor_tradable_holdout_rows"],1)
                self.assertEqual(result["issuers_with_5_consecutive_vendor_tradable_holdout_rows"],1)
                for i in (0,1):
                    (root/str(i)/"shard_0000"/"sh_600000.csv").write_text(raw.replace("2026-01-06,11,1","2026-01-06,11,0"))
                with self.assertRaisesRegex(ValueError,"consecutive vendor-tradable"):
                    audit(root,"2025-12-31")
                for i in (0,1):
                    (root/str(i)/"shard_0000"/"sh_600000.csv").write_text(raw)
                for i in (0,1):
                    (root/str(i)/"shard_0000"/"sh_600000.csv").write_text(raw.replace("11,1","11,0"))
                with self.assertRaisesRegex(ValueError,"vendor-tradable"):
                    audit(root,"2025-12-31")
                for i in (0,1):
                    (root/str(i)/"shard_0000"/"sh_600000.csv").write_text(raw)
                (root/"1"/"shard_0000"/"sh_600000.csv").write_text(raw.replace(",11",",12"))
                with self.assertRaisesRegex(ValueError,"conflicting duplicate"):
                    audit(root,"2025-12-31")

    def test_missing_archive_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):audit(path,"2025-12-31")
    def test_invalid_archive_commit_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(ValueError,"archive commit"):
                audit(path,"2025-12-31",archive_commit="mutable-main")

    def test_invalid_cutoff_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):audit(path,"not-a-date")
    def test_disjoint_issuers_cannot_fake_chronological_holdout(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            for i,(code,day) in enumerate((("sh.600000","2025-12-30"),("sh.600001","2026-01-02"))):
                d=base/str(i)/"shard_0000"
                d.mkdir(parents=True)
                (d/"quality.json").write_text("{}")
                (d/(code.replace(".","_")+".csv")).write_text("date,close\n"+day+",10\n")
            def valid(path):
                code="sh.600000" if path.parent.name=="0" else "sh.600001"
                return {"details":[{"code":code}]}
            with patch("collector.p4_real_p2_chronological_split.assess",side_effect=valid):
                with self.assertRaisesRegex(ValueError,"crosses research cutoff"):
                    audit(base,"2025-12-31")

if __name__=="__main__":unittest.main()
