import unittest,json
from collector.p3_resume_index_extension import select,SOURCES,stock_key
class IndexExtensionTests(unittest.TestCase):
    def test_exact(self):
        title=SOURCES["sh.605258"][3]
        r=dict(secCode="605258",announcementTitle=title,adjunctUrl="finalpage/2026-10-31/123.PDF",announcementTime=1)
        self.assertTrue(select(json.dumps(dict(hasMore=False,announcements=[r])),"sh.605258",title,"2026-10-30","2026-11-02")[1].endswith("123.PDF"))
    def test_incomplete(self):
        with self.assertRaises(ValueError):select('{"hasMore":true}',"sh.605258","x","2026-10-30","2026-11-02")

    def test_null_index(self):
        with self.assertRaisesRegex(ValueError,"empty or invalid"):select('{"hasMore":false,"announcements":null}',"sh.605258","x","2026-10-30","2026-11-02")
    def test_security_key(self):
        self.assertEqual(stock_key('[{"code":"000635","orgId":"gssz0000635"}]',"sz.000635"),"000635,gssz0000635")
    def test_wrong_security(self):
        with self.assertRaises(ValueError):stock_key('[{"code":"000636","orgId":"gssz0000636"}]',"sz.000635")
