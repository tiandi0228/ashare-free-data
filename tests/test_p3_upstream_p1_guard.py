"""A changed P1 run-name cannot break genuine P3 workflow provenance."""
import unittest

from collector.p3_upstream_p1_guard import p1_upstream_run_id


REPO="tiandi0228/ashare-free-data"


def event(**changes):
    record={
        "id": 42804267031,
        "name": "P1 origin 10 3 * * 1-5 [NO TRADES]",
        "conclusion": "success",
        "path": ".github/workflows/p1-fresh-vendor-roster.yml",
        "head_repository": {"full_name": REPO},
        "head_branch": "main",
        "event": "schedule",
    }
    record.update(changes)
    return record


class P1UpstreamGuardTests(unittest.TestCase):
    def test_accept_exact_workflow_despite_dynamic_display_name(self):
        self.assertEqual(p1_upstream_run_id(event(), REPO), 42804267031)
        self.assertEqual(
            p1_upstream_run_id(event(name="P1 origin push [NO TRADES]",
                                      event="push"), REPO), 42804267031)

    def test_reject_wrong_workflow_even_when_old_name_matches(self):
        invalid=event(name="P1 fresh Baostock mainboard roster observation (NO TRADES)",
                      path=".github/workflows/another-workflow.yml")
        with self.assertRaisesRegex(ValueError, "unexpected upstream"):
            p1_upstream_run_id(invalid, REPO)

    def test_reject_other_repo_branch_event_and_failed_execution(self):
        for altered in (
            {"head_repository": {"full_name": "somebody/fork"}},
            {"head_branch": "feature/unsafe"},
            {"event": "pull_request"},
            {"conclusion": "failure"},
            {"id": "42804267031"},
            {"id": 0},
            {"path": None},
            {"head_repository": None},
        ):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                p1_upstream_run_id(event(**altered), REPO)


if __name__ == "__main__":
    unittest.main()
