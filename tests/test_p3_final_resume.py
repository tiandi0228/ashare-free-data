import json,unittest
from collector.p3_final_resume import select
class FinalResumeTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(secCode="600185",orgId="g1",announcementTitle="重大资产重组暨股票复牌公告",adjunctUrl="finalpage/2026-11-26/123.PDF",announcementTime=1)
    def raw(self,rows=None,more=False):
        return json.dumps(dict(hasMore=more,announcements=[self.row] if rows is None else rows)).encode()
    def test_valid(self):
        self.assertEqual(select(self.raw(),"sh.600185","g1")[1],"https://static.cninfo.com.cn/finalpage/2026-11-26/123.PDF")
    def test_ambiguous(self):
        with self.assertRaises(ValueError):select(self.raw([self.row,self.row]),"sh.600185","g1")
    def test_wrong_org(self):
        with self.assertRaises(ValueError):select(self.raw(),"sh.600185","g2")
    def test_incomplete(self):
        with self.assertRaises(ValueError):select(self.raw(more=True),"sh.600185","g1")
    def test_attachment(self):
        self.row["adjunctUrl"]="https://other.example/a.pdf"
        with self.assertRaises(ValueError):select(self.raw(),"sh.600185","g1")
