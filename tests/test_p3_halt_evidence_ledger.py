import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p3_halt_evidence_ledger import reconcile

SAFE=dict(trade_gate="BLOCKED",orders=[],executable_candidates=[],officially_certified_halt_dates=0)
T=dict(target_date="2026-01-15",original_csv_sha256="a"*64)

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.q=dict(SAFE,target_days=1,tasks=[dict(code="sz.002931",targets=[T])])
        f=self.root/"p3_002931_notice_replay";f.mkdir()
        notices=[]
        for name in ("halt","resume"):
            raw=b"%PDF-"+name.encode()
            (f/(name+".pdf")).write_bytes(raw)
            notices.append(dict(filename=name+".pdf",sha256=hashlib.sha256(raw).hexdigest(),url="https://example.test/"+name))
        self.pair=dict(start="2026-01-14",resume="2026-01-19",notices=notices)
        self.write("p3_002931_notice_replay",dict(issuer="sz.002931",intervals=[self.pair],matched_targets=[T]))
        self.write("p3_600491_notice_replay",dict(issuer="sh.600491",targets=[],receipts=[]))
        self.write("p3_002969_retrospective_replay",dict(issuer="sz.002969",receipts=[],retrospective_matches=[]))
        self.write("p3_two_issuer_notice_leads",dict(receipts=[]))
    def write(self,name,data):
        f=self.root/name;f.mkdir(exist_ok=True)
        (f/"report.json").write_text(json.dumps(dict(SAFE,**data)))
    def test_pair_and_provenance(self):
        r=reconcile(self.q,self.root)
        self.assertEqual(r["complete_original_pair_days"],1)
        self.assertEqual(r["official_channel_supported_days"],1)
        self.assertEqual(len(r["rows"][0]["document_receipts"]),2)
        self.assertEqual(r["officially_certified_halt_dates"],0)
    def test_tampered_original(self):
        (self.root/"p3_002931_notice_replay/halt.pdf").write_bytes(b"%PDF-tampered")
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):reconcile(self.q,self.root)
    def test_incomplete_pair(self):
        self.pair["notices"].pop()
        self.write("p3_002931_notice_replay",dict(issuer="sz.002931",intervals=[self.pair],matched_targets=[T]))
        with self.assertRaisesRegex(ValueError,"invalid original pair"):reconcile(self.q,self.root)
    def test_unbound_target(self):
        self.write("p3_002931_notice_replay",dict(issuer="sz.002931",intervals=[self.pair],matched_targets=[dict(T,original_csv_sha256="b"*64)]))
        with self.assertRaisesRegex(ValueError,"unbound target"):reconcile(self.q,self.root)
