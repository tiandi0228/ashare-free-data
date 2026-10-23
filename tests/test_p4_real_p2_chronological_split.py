import unittest
from datetime import date
from collector.p4_real_p2_chronological_split import audit
class SplitTests(unittest.TestCase):
    def test_missing_archive_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):audit(path,"2025-12-31")
    def test_invalid_cutoff_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):audit(path,"not-a-date")
if __name__=="__main__":unittest.main()
