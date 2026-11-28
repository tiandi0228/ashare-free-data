import json,unittest
from collector.p4_residual_notice_discovery import candidates,stock_key
class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(secCode="002861",orgId="g1",announcementTitle="股票交易异常波动公告",adjunctUrl="finalpage/2026-11-12/123.PDF",announcementTime=1,announcementId="123")
    def raw(self,more=False):
        return json.dumps(dict(hasMore=more,announcements=[self.row])).encode()
    def test_valid(self):
        self.assertEqual(len(candidates(self.raw(),"sz.002861","g1","2026-11-11")),1)
    def test_wrong_org(self):
        self.assertEqual(candidates(self.raw(),"sz.002861","g2","2026-11-11"),[])
    def test_outside_window(self):
        self.row["adjunctUrl"]="finalpage/2026-11-19/123.PDF"
        self.assertEqual(candidates(self.raw(),"sz.002861","g1","2026-11-11"),[])
    def test_incomplete(self):
        with self.assertRaises(ValueError):candidates(self.raw(True),"sz.002861","g1","2026-11-11")
    def test_security(self):
        self.assertEqual(stock_key(b'[{"code":"002861","orgId":"g1"}]',"sz.002861"),"002861,g1")
