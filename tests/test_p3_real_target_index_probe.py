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
    def test_vendor_halt_window_is_bounded_and_no_pit_claim(self):
        seen=[]
        def feed(params):
            seen.append(params)
            return {"announcements":[],"hasMore":False}
        query("sh.600038",fetch_page=feed,observed_dates=["2026-09-14"])
        self.assertEqual(seen[0]["seDate"],"2026-07-31~2026-09-21")
    def test_run_passes_transition_as_evidence_search_not_clearance(self):
        q=self.sample()
        q["targets"]=[{"issuer":"sh.600038",
                       "vendor_halt_transition_research_days":["2026-09-14"],
                       "vendor_suspended_research_days":["2026-10-20"]}]
        seen=[]
        def fake(issuer,observed_dates=None):
            seen.append((issuer,observed_dates))
            return []
        r=run(q,fake)
        self.assertEqual(seen,[("sh.600038",["2026-09-14"])])
        self.assertTrue(r["results"][0]["historical_vendor_event_window_used"])
        self.assertFalse(r["historical_PIT_verified"])
    def test_vendor_future_date_rejected(self):
        with self.assertRaises(ValueError):
            query("sh.600038",fetch_page=lambda _:{"announcements":[]},
                  observed_dates=["2099-01-01"])
    def test_followup_window_exact_and_bounded(self):
        seen=[]
        def fetch(args):
            seen.append(args["seDate"])
            return {"announcements":[],"hasMore":False}
        self.assertEqual(query("sh.600319",fetch_page=fetch,
                               research_window=("2025-11-03","2026-02-01")),[])
        self.assertEqual(seen,["2025-11-03~2026-02-01"])
    def test_unbounded_future_or_reversed_followup_blocked(self):
        for period in (("2025-01-01","2026-05-01"),
                       ("2026-02-01","2025-11-01"),
                       ("2025-11-01","2099-02-01")):
            with self.assertRaises(ValueError):
                query("sh.600319",fetch_page=lambda _:{"announcements":[]},
                      research_window=period)
    def test_followup_cannot_override_vendor_window(self):
        with self.assertRaises(ValueError):
            query("sh.600319",observed_dates=["2025-11-04"],
                  research_window=("2025-11-03","2025-11-08"))
    def test_hard_page_cap(self):
        with self.assertRaises(ValueError):query("sh.600038",max_pages=MAX_PAGES+1)
        self.assertEqual(MAX_PAGES,3)
if __name__=="__main__":unittest.main()
