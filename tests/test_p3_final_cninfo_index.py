import unittest,json
from datetime import datetime,timezone
from collector.p3_final_cninfo_index import select,TITLE
class IndexTests(unittest.TestCase):
    def row(self):
        return dict(secCode="000972",orgId="gssz0000972",announcementTitle=TITLE,adjunctUrl="finalpage/2026-11-03/123.PDF",announcementTime=int(datetime(2026,11,2,16,tzinfo=timezone.utc).timestamp()*1000),announcementId="fixture")
    def test_exact(self):
        _,url,stamp=select(json.dumps(dict(hasMore=False,announcements=[self.row()])))
        self.assertEqual(stamp,"2026-11-03T00:00:00+08:00")
        self.assertTrue(url.startswith("https://static.cninfo.com.cn/"))
    def test_duplicate(self):
        with self.assertRaises(ValueError):select(json.dumps(dict(hasMore=False,announcements=[self.row(),self.row()])))
    def test_wrong_path(self):
        r=self.row();r["adjunctUrl"]="../bad.pdf"
        with self.assertRaises(ValueError):select(json.dumps(dict(hasMore=False,announcements=[r])))
    def test_incomplete(self):
        with self.assertRaises(ValueError):select(json.dumps(dict(hasMore=True,announcements=[self.row()])))
