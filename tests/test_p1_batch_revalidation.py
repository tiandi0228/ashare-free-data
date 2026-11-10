"""Regression: P1 batch proposals must be fresh and exact before any future copy."""
import copy
import unittest

from collector.p1_batch_revalidation import revalidate
from tests.test_p1_bounded_missing_shard_batch_plan import BoundedBatchTests, COMMIT


class BatchRevalidationTests(BoundedBatchTests):
    def test_frozen_proposal_passes_without_write_authorization(self):
        proposal = self.plan(max_shards=2)
        x = revalidate(proposal, self.handoff, self.source, self.target, COMMIT, COMMIT)
        self.assertEqual(x["status"], "PROPOSAL_UNCHANGED_READ_ONLY_NOT_AUTHORIZED")
        self.assertEqual(x["selected_file_count"], 4)
        self.assertIs(x["writer_cutover_authorized"], False)
        self.assertIs(x["automatic_copy_authorized"], False)
        self.assertEqual(x["trade_gate"], "BLOCKED")

    def test_after_staging_first_file_old_proposal_expires(self):
        proposal = self.plan(max_shards=2)
        self.mirror(proposal["selected_missing_files"][0]["path"])
        with self.assertRaisesRegex(ValueError, "stale"):
            revalidate(proposal, self.handoff, self.source, self.target, COMMIT, COMMIT)

    def test_changed_source_target_commits_and_selection_rejected(self):
        proposal = self.plan()
        for sc, tc in (("c" * 40, COMMIT), (COMMIT, "d" * 40)):
            with self.subTest(source=sc, target=tc):
                with self.assertRaisesRegex(ValueError, "stale"):
                    revalidate(proposal, self.handoff, self.source, self.target, sc, tc)
        altered = copy.deepcopy(proposal)
        altered["selected_missing_files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "stale"):
            revalidate(altered, self.handoff, self.source, self.target, COMMIT, COMMIT)

    def test_mutated_source_or_conflicting_target_rejected(self):
        proposal = self.plan()
        rel = proposal["selected_missing_files"][0]["path"]
        (self.source / rel).write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            revalidate(proposal, self.handoff, self.source, self.target, COMMIT, COMMIT)
        self.source.joinpath(rel).write_bytes(
            b'{"trade_gate":"BLOCKED"}' if rel.endswith("quality.json")
            else b""
        )
        self.mirror(rel)
        self.target.joinpath(rel).write_bytes(b"conflict")
        with self.assertRaises(ValueError):
            revalidate(proposal, self.handoff, self.source, self.target, COMMIT, COMMIT)

    def test_untrusted_limits_and_approval_flags_rejected(self):
        proposal = self.plan()
        for key, value in (("writer_cutover_authorized", True),
                           ("automatic_copy_authorized", True),
                           ("batch_max_shards", 5),
                           ("selected_file_count", 99),
                           ("executable_candidates", ["sh.600000"])):
            altered = copy.deepcopy(proposal)
            altered[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                revalidate(altered, self.handoff, self.source, self.target, COMMIT, COMMIT)


if __name__ == "__main__":
    unittest.main()
