import unittest
from datetime import date
from collector.p3_resume_followup_discovery import discover,targets

def ledger():
    records=[]
    for issuer,day in [("sh.600302","2026-04-30"),("sh.600303","2025-04-18"),
                       ("sh.600319","2025-11-04"),("sh.600322","2024-12-18"),
                       ("sh.600323","2026-04-22"),("sh.600331","2024-12-04")]:
        records.append({"issuer":issuer,"halt_text_date":day,
            "original_pdf_sha256":"a"*64,"halt_announcement_id":"1222222222",
            "historical_halt_interval_certified":False,
            "warning":"NO_RESUME_IN_BOUNDED_ARCHIVE_IS_NOT_PROOF_OF_CONTINUING_HALT"})
    return {"phase":"P3_DURABLE_ORIGINAL_EVENT_EPISODE_RESEARCH",
            "trade_gate":"BLOCKED","orders":[],
            "historical_PIT_verified":False,"official_PIT_cells_certified":0,
            "complete_issuer_halt_intervals_certified":False,
            "unpaired_halt_starts_needing_resumption_search":6,
            "official_resumption_followups":records}

def source_notice(issuer,ident,title):
    return {"announcement_id":ident,
            "announcement_title_unverified":title,
            "official_pdf_url":f"https://static.cninfo.com.cn/finalpage/2025-06-01/{ident}.PDF",
            "historical_PIT_verified":False}

class Followups(unittest.TestCase):
    def test_two_runs_cover_all_six_without_forged_status(self):
        one=targets(ledger(),1,today=date(2026,10,26))
        two=targets(ledger(),2,today=date(2026,10,26))
        self.assertEqual(len(one),3)
        self.assertEqual(len(two),3)
        self.assertEqual({x["issuer"] for x in one+two},
                         {r["issuer"] for r in ledger()["official_resumption_followups"]})
        self.assertTrue(all(x["source_halt_certified"] is False for x in one+two))
    def test_official_title_match_is_not_effective_resume(self):
        seen=[]
        def client(issuer,max_pages,research_window):
            seen.append((issuer,max_pages,research_window))
            return [source_notice(issuer,"123123123","股票复牌公告"),
                    source_notice(issuer,"123123124","公司关于尚未复牌的风险提示"),
                    source_notice(issuer,"123123125","股东权益变动公告")]
        r=discover(ledger(),1,client,today=date(2026,10,26))
        self.assertEqual(r["attempted"],3)
        self.assertEqual(sum(x["candidate_count"] for x in r["results"]),3)
        self.assertEqual(len(seen),3)
        self.assertTrue(all(x[1]==2 for x in seen))
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_error_does_not_clear_missing_resume(self):
        def broken(*a,**kw):raise TimeoutError("remote index outage")
        r=discover(ledger(),1,broken,today=date(2026,10,26))
        self.assertTrue(all(x["status"]=="INDEX_UNAVAILABLE_NOT_NO_RESUMPTION" for x in r["results"]))
        self.assertFalse(r["complete_issuer_halt_intervals_certified"])
    def test_untrusted_PIT_on_existing_episode_fails(self):
        q=ledger();q["official_PIT_cells_certified"]=1
        with self.assertRaises(ValueError):discover(q,1,lambda *a,**kw:[],today=date(2026,10,26))
    def test_forged_resume_candidate_status_not_accepted(self):
        def unsafe(issuer,max_pages,research_window):
            x=source_notice(issuer,"100000001","关于复牌")
            x["historical_PIT_verified"]=True
            return [x]
        r=discover(ledger(),1,unsafe,today=date(2026,10,26))
        self.assertEqual(r["results"][0]["status"],"INDEX_UNAVAILABLE_NOT_NO_RESUMPTION")
    def test_future_halt_date_rejected(self):
        q=ledger();q["official_resumption_followups"][0]["halt_text_date"]="2099-01-01"
        with self.assertRaises(ValueError):targets(q,1,today=date(2026,10,26))
    def test_research_window_never_extends_unbounded(self):
        r=discover(ledger(),1,lambda *a,**kw:[],today=date(2026,10,26))
        for item in r["selected_halt_sources"]:
            start=date.fromisoformat(item["search_window_start"])
            end=date.fromisoformat(item["search_window_end"])
            self.assertLessEqual((end-start).days,91)
    def test_empty_missing_halt_queue_fails(self):
        q=ledger();q["official_resumption_followups"]=[];q["unpaired_halt_starts_needing_resumption_search"]=0
        with self.assertRaises(ValueError):discover(q,1,lambda *a,**kw:[],today=date(2026,10,26))
if __name__=="__main__":unittest.main()
