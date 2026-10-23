import tempfile,unittest,json,hashlib
from pathlib import Path
from collector.p4_sse_offline_replay import replay
class Tests(unittest.TestCase):
    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):replay(d)
    def test_tampered_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=b"original";(root/"sse_2024.html").write_bytes(b"tampered")
            r={"year":2024,"status":"CAPTURED_OFFICIAL_HOST_CONTENT_UNVERIFIED",
               "filename":"sse_2024.html","sha256":hashlib.sha256(raw).hexdigest()}
            (root/"manifest.json").write_text(json.dumps({"trade_gate":"BLOCKED","expected_count":3,"receipts":[r,r,r]}))
            with self.assertRaises(ValueError):replay(root)
if __name__=="__main__":unittest.main()
