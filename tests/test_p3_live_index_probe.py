import unittest
from collector.p3_live_index_probe import normalize
class IndexTests(unittest.TestCase):
    def test_matching_original(self):
        r=normalize({"announcements":[{"announcementId":"1223557376","secCode":"603014","adjunctUrl":"finalpage/2025-05-16/1223557376.PDF","announcementTime":1747380000000}]},"1223557376")
        self.assertEqual(r[0]["issuer"],"sh.603014")
        self.assertEqual(r[0]["timestamp_type"],"UNAUTHENTICATED_INDEX_MILLISECONDS")
    def test_invalid_shape(self):
        with self.assertRaises(ValueError):normalize({"error":"blocked"},"123")
    def test_duplicate_rejected(self):
        a={"announcementId":"123","secCode":"600000","adjunctUrl":"finalpage/2026-10-20/123.PDF"}
        with self.assertRaises(ValueError):normalize({"announcements":[a,a]},"123")
if __name__=="__main__":unittest.main()
