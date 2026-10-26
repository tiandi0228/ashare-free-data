import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p3_real_p1_pdf_replay import audit
class ReplayTests(unittest.TestCase):
    def test_replay_and_detect_modified_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=b"%PDF-"+b"x"*3100
            name="sz_000001_123456789.pdf";(root/name).write_bytes(raw)
            q={"phase":"P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE","trade_gate":"BLOCKED",
               "attempted":1,"retrieved":1,"sources":[{"issuer":"sz.000001",
               "announcement_id":"123456789",
               "url":"https://static.cninfo.com.cn/finalpage/2026-01-01/123456789.PDF",
               "original_bytes_verified":True,"original_file":name,
               "sha256":hashlib.sha256(raw).hexdigest(),"observed_at_utc":"2026-10-26T00:00:00Z",
               "historical_PIT_verified":False,"historical_first_publication_authenticated":False}]}
            (root/"quality.json").write_text(json.dumps(q))
            self.assertEqual(audit(root)["independently_sha_verified"],1)
            (root/name).write_bytes(raw+b"tamper")
            with self.assertRaisesRegex(ValueError,"SHA mismatch"):audit(root)
if __name__=="__main__":unittest.main()
