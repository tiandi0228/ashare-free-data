import hashlib
import json
import unittest

from collector.p1_single_gap_acceptance import WORKFLOW, verify


class SingleGapAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.workflow, self.archive = "a" * 40, "b" * 40
        source = "c" * 64
        self.csv = b"example original"
        digest = lambda raw: hashlib.sha256(raw).hexdigest()
        code = "sz.000001"
        manifest = digest((code + "\n").encode())
        quality = dict(results=[dict(code=code, status="OBSERVED_UNVERIFIED", sha256=digest(self.csv))],
                       manifest_sha256=manifest, status="OBSERVED_SUBSET_UNVERIFIED", trade_gate="BLOCKED")
        self.quality = json.dumps(quality, indent=2).encode()
        row = dict(index=1, issuer_count=1, manifest_sha256=manifest,
                   receipt_sha256=digest(json.dumps(quality, sort_keys=True).encode()))
        self.live = dict(phase="P1_ROSTER_SHARD_LEDGER", trade_gate="BLOCKED", source_sha256=source,
                         historical_PIT_verified=False, orders=[], executable_candidates=[],
                         shard_count=2, completed=[row], completed_shards=1, completed_issuers=1,
                         pending_shards=[0], next_shard=0, failed_in_this_reconciliation=[],
                         full_market_bars_certified=False)
        self.run_meta = dict(id=123, run_attempt=2, event="workflow_dispatch", path=WORKFLOW,
                             head_branch="main", head_sha=self.workflow, status="completed", conclusion="success")
        self.receipt = dict(status="MANUAL_GAP_ARCHIVE_AND_CHECKPOINT_VERIFIED", run_id="123",
                            run_attempt="2", workflow_sha=self.workflow, archive_audit_commit=self.archive,
                            source_sha256=source, selected_shards=[1], new_shards_durably_accepted=1,
                            accepted_shards=[row], remote_readback_verified=True, historical_PIT_verified=False,
                            trade_gate="BLOCKED", orders=[], executable_candidates=[], checkpoint_blob_sha="c"*40)
        self.status = dict(source_sha256=source, trade_gate="BLOCKED", archived_shards=[1])

    def check(self, **overrides):
        args = dict(run=self.run_meta, receipt=self.receipt, live=self.live, quality=self.quality,
                    archive_status=self.status, read_csv=lambda code: self.csv)
        return verify(**(args | overrides), shard=1, workflow_sha=self.workflow, archive_sha=self.archive)

    def test_verifies_canonical_receipt_and_original_bytes(self):
        self.assertEqual(self.check()["status"], "SINGLE_SHARD_MANUAL_ACCEPTANCE_READBACK_VERIFIED")

    def test_refuses_synthetic_claims_or_wrong_attempt(self):
        for field, value in (("event", "schedule"), ("run_attempt", 3), ("head_branch", "pr"),
                             ("conclusion", "failure"), ("head_sha", "f"*40)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(run=self.run_meta | {field: value})

    def test_refuses_wrong_shard_or_missing_archival_evidence(self):
        for override in (dict(receipt=self.receipt | {"selected_shards": [0, 1]}),
                         dict(quality=b"{}"), dict(read_csv=lambda _: b"modified"),
                         dict(archive_status=self.status | {"archived_shards": []})):
            with self.subTest(fields=list(override)), self.assertRaises(ValueError):
                self.check(**override)
