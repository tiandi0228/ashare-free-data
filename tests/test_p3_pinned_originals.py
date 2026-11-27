import hashlib,unittest
from collector.p3_pinned_originals import check_bytes
class PinnedTests(unittest.TestCase):
    def test_valid(self):
        raw=b"%PDF-test";check_bytes(raw,hashlib.sha256(raw).hexdigest())
    def test_tampered(self):
        with self.assertRaises(ValueError):check_bytes(b"%PDF-changed",hashlib.sha256(b"%PDF-test").hexdigest())
    def test_html(self):
        raw=b"<html>"; 
        with self.assertRaises(ValueError):check_bytes(raw,hashlib.sha256(raw).hexdigest())
