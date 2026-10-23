import tempfile,unittest
from collector.p4_vendor_session_coverage import audit
class Tests(unittest.TestCase):
    def test_empty_archive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):audit(d)
if __name__=="__main__":unittest.main()
