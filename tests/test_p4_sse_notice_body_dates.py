import unittest
from collector.p4_sse_notice_body_dates import inspect
class TestNoticeBody(unittest.TestCase):
    def test_missing_real_body_is_not_certified(self):
        x=inspect(2026,b"<html><body>hello</body></html>")
        self.assertTrue(x["ranges_missing_textual_dates"])
        self.assertFalse(x["body_semantically_authenticated"])
    def test_2024_date_mentions_can_be_inspected(self):
        from collector.p4_sse_holiday_crosscheck import HOLIDAY_RANGES
        parts=[]
        for start,end in HOLIDAY_RANGES[2024]:
            for day in (start,end):
                _,m,d=map(int,day.split("-"));parts.append(f"{m}月{d}日")
        x=inspect(2024,("".join(parts)).encode())
        self.assertFalse(x["ranges_missing_textual_dates"])
        self.assertFalse(x["body_semantically_authenticated"])
if __name__=="__main__":unittest.main()
