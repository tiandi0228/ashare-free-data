"""Ensure only explicit manual dispatch controls focused P1 selection."""
import json
import os
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/p1-fresh-vendor-roster.yml"


class ManualOnlyGapIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=WORKFLOW.read_text()

    def test_gap_control_is_optional_manual_dispatch(self):
        s=self.source
        self.assertIn('      gap_window:\n',s)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.gap_window || ''",s)
        self.assertIn('[[ "${GITHUB_EVENT_NAME}" == "workflow_dispatch" ]]',s)
        self.assertIn('GAP_ARGS=(--gap-window "$P1_GAP_WINDOW")',s)
        self.assertIn('"${GAP_ARGS[@]}" --per-run "$P1_REQUESTED_SHARDS"',s)

    def test_scheduled_trigger_still_exists_and_is_not_conditional(self):
        s=self.source
        self.assertIn("  schedule:\n",s)
        self.assertIn("    - cron: '10 0 * * 1-5'",s)
        self.assertIn("    - cron: '10 15 * * 6,0'",s)
        self.assertIn("concurrency:\n  group: p1-fresh-mainboard-roster-serial",s)

    def test_provenance_and_archival_checks_remain(self):
        s=self.source
        self.assertIn("Recover durable same-version GitHub checkpoint",s)
        self.assertIn("Recover previously archived but uncheckpointed research shards",s)
        self.assertIn("Record bounded pilot selection for audit",s)
        self.assertIn('requested=int(os.environ["P1_REQUESTED_SHARDS"])',s)

    def test_no_auto_launch_or_unlock(self):
        s=self.source
        self.assertNotIn("trade_gate: OPEN",s)
        self.assertIn("P1_GAP_WINDOW:",s)
        self.assertIn("      - name: Offline source tests",s)

    def test_manual_gap_replay_rejects_missing_shard_before_checkpoint(self):
        audit=self.source.index('      - name: Audit permanent research CSV')
        persist=self.source.index('      - name: Persist durable no-trade checkpoint')
        ack=self.source.index('      - name: Verify remote checkpoint preserved')
        self.assertLess(audit,persist)
        self.assertLess(persist,ack)
        py=self.source[audit:persist].split("python - <<'PY'\n",1)[1].split("\n          PY",1)[0]
        from textwrap import dedent
        script=compile(dedent(py),'workflow_archive_audit','exec')
        paths={
            'evidence/archive_audit.json': {
                'trade_gate':'BLOCKED','historical_PIT_verified':False,
                'archive_csv_replay_enabled':True,'archived_issuers':8,
                'ledger_issuers':16,'archive_repair_queue':[220],
            },
            'evidence/pilot_selection.json': {'selected_shards':[220,225]},
            'evidence/ledger.json': {'completed':[{'index':220}]},
        }
        def read(path):
            return json.dumps(paths[str(path)])
        with patch.object(Path,'read_text',read), patch.dict(os.environ,{'P1_GAP_WINDOW':'220:225'}):
            with self.assertRaisesRegex(ValueError,'missing replayed archive'):
                exec(script,{})
            # The second shard is optional and uncredited when it was not in
            # the ledger. Only archived evidence for the first is required.
            paths['evidence/archive_audit.json']['archive_repair_queue']=[225]
            exec(script,{})

    def test_manual_gap_requires_exact_remote_evidence_after_checkpoint(self):
        from textwrap import dedent
        section=self.source.split('      - name: Verify remote checkpoint preserved',1)[1].split('      - name:',1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && env.P1_GAP_WINDOW != ''",section)
        py=section.split("python - <<'PY'\n",1)[1].split("\n          PY",1)[0]
        script=compile(dedent(py),'workflow_checkpoint_ack','exec')
        from collector.p1_checkpoint import epoch_path
        source='a'*64
        proposed={'source_sha256':source,'shard_count':400,
                  'completed':[{'index':220,'receipt_sha256':'b'*64}],
                  'completed_shards':1}
        extra={'index':225,'receipt_sha256':'c'*64}
        files={'ledger.json':proposed,'prior_ledger.json':{'completed':[]},
               'pilot_selection.json':{'selected_shards':[220,225]}}
        env={'GITHUB_REPOSITORY':'owner/repo','GITHUB_RUN_ID':'12',
             'GITHUB_RUN_ATTEMPT':'2','GITHUB_SHA':'d'*40}
        def read(path):
            return json.dumps(files[path.name])
        with patch.object(Path,'read_text',read), \
             patch.object(Path,'write_text') as write, \
             patch('subprocess.check_output',return_value='a'*40+'\n'), \
             patch.dict(os.environ,env), \
             patch('collector.p1_checkpoint.validate'), \
             patch('collector.p1_checkpoint.remote_read') as remote:
            remote.return_value=(None,None)
            with self.assertRaisesRegex(ValueError,'not found'):
                exec(script,{})
            for completed in ([],[{**proposed['completed'][0],'receipt_sha256':'f'*64}]):
                remote.return_value=({**proposed,'completed':completed},'blob')
                with self.assertRaisesRegex(ValueError,'evidence mismatch'):
                    exec(script,{})
            remote.return_value=({**proposed,'source_sha256':'d'*64},'blob')
            with self.assertRaisesRegex(ValueError,'epoch mismatch'):
                exec(script,{})
            remote.return_value=({**proposed,'completed':proposed['completed']+[extra]},'blob')
            exec(script,{})
            remote.assert_called_with('owner/repo',epoch_path(source))
            write.assert_called_once()
            result=json.loads(write.call_args.args[0])
            self.assertEqual(result['accepted_shards'],proposed['completed'])
            self.assertEqual(result['selected_shards'],[220,225])
            self.assertEqual(result['archive_audit_commit'],'a'*40)
            self.assertEqual(result['checkpoint_blob_sha'],'blob')
            self.assertEqual(result['trade_gate'],'BLOCKED')
            files['prior_ledger.json']['completed']=proposed['completed']
            with self.assertRaisesRegex(ValueError,'did not add'):
                exec(script,{})
            write.assert_called_once()


if __name__=="__main__":
    unittest.main()
