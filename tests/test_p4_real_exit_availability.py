import tempfile,unittest
from collector.p4_real_exit_availability import audit
class Tests(unittest.TestCase):
    def test_no_real_archive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):audit(d)
if __name__=="__main__":unittest.main()
