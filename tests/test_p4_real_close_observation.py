import tempfile,unittest
from collector.p4_real_close_observation import replay
class CloseTests(unittest.TestCase):
    def test_no_originals_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):replay(d)
if __name__=="__main__":unittest.main()
