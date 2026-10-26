import unittest
from collector.p3_real_target_index_probe import run,query,MAX_PAGES

def row(issuer="sh.600038",num="123456789",title=""):
    return {"secCode":issuer[-6:],"announcementId":num,
            "adjunctUrl":f"finalpage/2026-10-20/{num}.PDF",
            "announcementTitle":title,"announcementTime":1792500000000}
class ProbeTests(unittest.TestCase):
    def sample(self):
        return {"phase":"P3_REAL_P1_UNMATCHED_OFFICIAL_DISCOVERY_QUEUE","trade_gate":"BLOCKED",
                "targets":[{"issuer":"sz.000001"},{"issuer":"sh.600000"}]}
    def test_distinct_issuer_lookup_and_no_pit(self):
        r=run(self.sample(),lambda x:[])
        self.assertEqual(r["attempted"],2)
        self.assertEqual(r["results"][0]["status"],"NO_INDEX_MATCH_NOT_NO_RISK")
        self.assertFalse(r["historical_PIT_verified"])
        self.assertFalse(r["index_exhaustive_or_historical_asof_proof"])
    def test_unavailable_is_not_clearance(self):
        def bad(x):raise TimeoutError("unavailable")
        self.assertEqual(run(self.sample(),bad)["results"][0]["status"],"INDEX_UNAVAILABLE_NOT_NO_RISK")
    def test_second_page_risk_notice_retained(self):
        calls=[]
        def feed(params):
            calls.append(params)
            if params["pageNum"]==1:
                return {"announcements":[row(num=str(111111000+i)) for i in range(30)],"hasMore":True}
            return {"announcements":[row(num="222222222",title="关于股票停牌的公告")],"hasMore":False}
        docs=query("sh.600038",fetch_page=feed)
        self.assertEqual(len(docs),31)
        self.assertEqual(docs[-1]["index_page_observed"],2)
        self.assertEqual(docs[-1]["announcement_title_unverified"],"关于股票停牌的公告")
        self.assertEqual([x["pageNum"] for x in calls],[1,2])
        self.assertTrue(all(x["column"]=="sse" for x in calls))
    def test_duplicate_notice_not_double_counted(self):
        original=[row(num=str(111110000+i)) for i in range(30)]
        docs=query("sh.600038",fetch_page=lambda p:
             {"announcements":original if p["pageNum"]==1 else [original[0]],"hasMore":p["pageNum"]==1})
        self.assertEqual(len(docs),30)
    def test_server_not_exhaustive_or_empty_is_no_risk(self):
        docs=query("sh.600038",fetch_page=lambda p:{"announcements":[],"hasMore":False})
        self.assertEqual(docs,[])
        with self.assertRaises(ValueError):
            query("sh.600038",fetch_page=lambda p:{"not_announcements":[]})
    def test_foreign_issuer_is_filtered_not_assumed(self):
        docs=query("sh.600038",fetch_page=lambda p:{"announcements":[row(issuer="sz.000001")],"hasMore":False})
        self.assertEqual(docs,[])
    def test_hard_page_cap(self):
        with self.assertRaises(ValueError):query("sh.600038",max_pages=MAX_PAGES+1)
        self.assertEqual(MAX_PAGES,3)
if __name__=="__main__":unittest.main()
