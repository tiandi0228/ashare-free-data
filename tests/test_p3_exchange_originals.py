import unittest
from collector.p3_exchange_originals import verify,official_urls
class OriginalsTests(unittest.TestCase):
    def test_normalize(self):
        self.assertTrue(verify("603595 2026－053 撤销其他风险警示 11 月 25 日",("603595","2026-053","撤销其他风险警示","11月25日")))
    def test_wrong_date(self):
        self.assertFalse(verify("603595 11月26日",("603595","11月25日")))

    def test_official_hosts(self):
        urls=official_urls("2026-11-25/603595_20261125_PDI4.pdf")
        self.assertEqual(len(urls),2)
        self.assertTrue(urls[1].startswith("https://big5.sse.com.cn/"))
        with self.assertRaises(ValueError):official_urls("../unknown.pdf")
