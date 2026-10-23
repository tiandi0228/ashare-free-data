import tempfile,unittest
from collector.p4_real_next_row_gate import replay
class NextRowTests(unittest.TestCase):
    def test_no_archived_receipts_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):replay(d)
if __name__=="__main__":unittest.main()
