import unittest,json
from collector.p3_resume_index_extension import select,SOURCES
class IndexExtensionTests(unittest.TestCase):
    def test_exact(self):
        title=SOURCES["sh.605258"][3]
        r=dict(secCode="605258",announcementTitle=title,adjunctUrl="finalpage/2026-10-31/123.PDF",announcementTime=1)
        self.assertTrue(select(json.dumps(dict(hasMore=False,announcements=[r])),"sh.605258",title,"2026-10-30","2026-11-02")[1].endswith("123.PDF"))
    def test_incomplete(self):
        with self.assertRaises(ValueError):select('{"hasMore":true}',"sh.605258","x","2026-10-30","2026-11-02")
