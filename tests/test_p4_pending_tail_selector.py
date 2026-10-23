import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from collector.p4_pending_tail_selector import select

class SelectorTests(unittest.TestCase):
    def fixture(self,root,valid=True):
        folder=Path(root)/"p4-tail-backfill/actions-123"
        folder.mkdir(parents=True)
        raw=b"original tail csv"
        (folder/"sh_600001_tail.csv").write_bytes(raw)
        receipt={"results":[{"code":"sh.600001","status":"OBSERVED_RESEARCH_ONLY",
                  "filename":"sh_600001_tail.csv","rows":1,"sha256":hashlib.sha256(raw).hexdigest()}]}
        (folder/"backfill_attempt.json").write_text(json.dumps(receipt))
        verified={"trade_gate":"BLOCKED","archive_merged":False,
                  "row_date_details":[{"code":"sh.600001","rows":1,
                  "restored_exit_date_observations":1 if valid else 0}]}
        (folder/"independent_verification.json").write_text(json.dumps(verified))
    def source(self):
        return {"tail_backfill_requests":[{"code":"sh.600001"},{"code":"sh.600002"}],
                "verified_issuers":192,"missing_beyond_source_end":600}
    def test_skips_valid_source_and_selects_failed_unarchived(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root)
            with patch("collector.p4_pending_tail_selector.audit",return_value=self.source()):
                first=select(root)
                second=select(root)
            self.assertEqual(first,second)
            self.assertEqual(first["selected_codes"],["sh.600002"])
            self.assertEqual(first["source_verified_issuers"],192)
            self.assertEqual(first["archived_issuers"],1)
    def test_never_marks_unmatched_archived_tail_completed(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root,valid=False)
            with patch("collector.p4_pending_tail_selector.audit",return_value=self.source()):
                with self.assertRaisesRegex(ValueError,"unverified or unmatched"):
                    select(root)
    def test_corrupted_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root)
            (Path(root)/"p4-tail-backfill/actions-123/sh_600001_tail.csv").write_bytes(b"corrupt")
            with patch("collector.p4_pending_tail_selector.audit",return_value=self.source()):
                with self.assertRaisesRegex(ValueError,"hash mismatch"):
                    select(root)

if __name__=="__main__":unittest.main()
