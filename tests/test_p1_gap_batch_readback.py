import unittest

from collector.p1_gap_batch_readback import compare


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.before = {0: {"receipt": "old"}}
        self.prior = dict(source_sha256="scope", completed_shards=1,
                          total_shards=10, archive_original_csvs_replayed=True)

    def check(self, after, selected):
        return compare(self.prior, dict(self.prior, completed_shards=len(after)),
                       self.before, after, selected)

    def test_full_partial_and_unrelated_changes(self):
        after = {**self.before, 2: {}, 3: {}, 4: {}}
        for chosen, accepted, remaining, unrelated in [
            ([2, 3], [2, 3], [], [4]), ([2, 7], [2], [7], [3, 4]),
            ([7, 8], [], [7, 8], [2, 3, 4]),
        ]:
            with self.subTest(chosen=chosen):
                out = self.check(after, chosen)
                self.assertEqual(out["selected_durably_present"], accepted)
                self.assertEqual(out["selected_still_missing"], remaining)
                self.assertEqual(out["unrelated_new_shards"], unrelated)
                self.assertFalse(out["workflow_run_attribution_verified"])
                self.assertEqual(out["trade_gate"], "BLOCKED")

    def test_reject_old_receipt_regression_or_already_accepted_selection(self):
        for after, selected in [({}, [2]), ({0: {}, 2: {}}, [2]), (self.before, [0])]:
            with self.subTest(after=after), self.assertRaises(ValueError):
                self.check(after, selected)

    def test_require_same_epoch_and_original_replay(self):
        for changes in (dict(source_sha256="other"), dict(archive_original_csvs_replayed=False)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                compare(self.prior, {**self.prior, **changes}, self.before, self.before, [2])
