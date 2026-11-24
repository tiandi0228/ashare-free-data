import unittest
from collector.p2_p3_artifact_source_select import choose_run, resolve


def run(id, conclusion="success", event="workflow_run"):
    return {"databaseId": id, "conclusion": conclusion, "event": event}


def artifact(name, expired=False, size=100):
    return {"name": name, "expired": expired, "size_in_bytes": size}


class ArtifactSourceTests(unittest.TestCase):
    def test_skipped_p2_evidence_falls_back_to_last_real_artifact(self):
        # The most recent P2 workflow has conclusion=success, but its replay
        # job is skipped, hence no p2-original-gap-triage artifact.
        rows = [run(45310206551), run(45299668642), run(45270000000, "failure")]
        seen = {}
        def lookup(i):
            seen[i] = True
            return [] if i == 45310206551 else [
                artifact("p2-original-gap-triage-" + str(i))]
        self.assertEqual(choose_run(rows, lookup, "p2-original-gap-triage-"),
                         45299668642)
        self.assertIn(45310206551, seen)

    def test_current_p3_source_has_genuine_evidence_artifact(self):
        rows = [run(45246691330)]
        self.assertEqual(choose_run(rows, lambda i: [
            artifact("p3-full-p1-official-scout-" + str(i))],
            "p3-full-p1-official-scout-"), 45246691330)

    def test_preferred_trigger_must_still_have_artifact(self):
        rows = [run(4), run(3)]
        lookup = lambda i: [] if i == 3 else [artifact("p2-original-gap-triage-4")]
        self.assertEqual(choose_run(rows, lookup, "p2-original-gap-triage-", 3), 4)

    def test_expired_zero_byte_wrong_named_and_pr_are_excluded(self):
        rows = [run(9), run(8), run(7), run(6, event="pull_request"), run(5)]
        def lookup(i):
            if i == 9:
                return [artifact("p2-original-gap-triage-9", expired=True)]
            if i == 8:
                return [artifact("p2-original-gap-triage-8", size=0)]
            if i == 7:
                return [artifact("wrong-name-7")]
            return [artifact("p2-original-gap-triage-" + str(i))]
        self.assertEqual(choose_run(rows, lookup, "p2-original-gap-triage-"), 5)
        with self.assertRaisesRegex(ValueError, "no successful"):
            choose_run(rows[:3], lookup, "p2-original-gap-triage-")

    def test_duplicate_or_ambiguous_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate GitHub"):
            choose_run([run(2),run(2)], lambda _: [], "p2-original-gap-triage-")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            choose_run([run(2)],lambda _: [
                artifact("p2-original-gap-triage-2"), artifact("p2-original-gap-triage-2")],
                "p2-original-gap-triage-")

    def test_two_sources_are_artifact_backed_without_pit_promotion(self):
        runs = {
            "p2-original-gap-window-triage.yml": [run(45310206551),run(45299668642)],
            "p3-full-p1-official-scout.yml": [run(45246691330)],
        }
        def lookup(i):
            if i == 45310206551:
                return []
            label = ("p2-original-gap-triage-" if i == 45299668642
                     else "p3-full-p1-official-scout-")
            return [artifact(label + str(i))]
        result = resolve(lambda w: runs[w],lookup)
        self.assertEqual((result["p2_run_id"],result["p3_run_id"]),
                         (45299668642,45246691330))
        self.assertFalse(result["official_PIT_certified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])


if __name__ == "__main__":
    unittest.main()
