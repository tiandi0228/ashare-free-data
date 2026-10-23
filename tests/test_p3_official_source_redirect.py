import unittest
from urllib.request import Request
from collector.p3_free_official_multi_issuer_probe import OfficialRedirects

class OfficialSourceRedirectTests(unittest.TestCase):
    def test_reject_external_unsafe_redirect(self):
        handler=OfficialRedirects()
        req=Request("https://static.cninfo.com.cn/finalpage/test.pdf")
        for destination in ("https://example.org/fake.pdf","http://static.cninfo.com.cn/fake.pdf","https://static.cninfo.com.cn.evil.com/file"):
            with self.assertRaises(ValueError):
                handler.redirect_request(req,None,302,"Found",{},destination)
    def test_allow_same_official_host(self):
        handler=OfficialRedirects()
        req=Request("https://static.cninfo.com.cn/finalpage/test.pdf")
        dest=handler.redirect_request(req,None,302,"Found",{},"https://static.cninfo.com.cn/finalpage/other.pdf")
        self.assertIn("static.cninfo.com.cn",dest.full_url)
if __name__=="__main__":unittest.main()
