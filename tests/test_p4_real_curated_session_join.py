import tempfile,unittest
from collector.p4_real_curated_session_join import audit
class Tests(unittest.TestCase):
    def test_missing_real_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as p:
            with self.assertRaises(ValueError):audit(p)
if __name__=="__main__":unittest.main()
