import unittest
from datetime import date
from collector.p3_resume_followup_discovery import discover,targets,window_for_halt

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
    def test_later_window_cycle_reaches_dates_beyond_first_90_days(self):
        first,_i,_n=window_for_halt(date(2025,11,4),date(2026,10,26),0)
        next_window,second,total=window_for_halt(date(2025,11,4),date(2026,10,26),1)
        self.assertEqual(first[0],"2025-11-03")
        self.assertEqual(first[1],"2026-02-01")
        self.assertEqual(next_window[0],"2026-02-02")
        self.assertEqual(second,1)
        self.assertGreaterEqual(total,3)
        self.assertLessEqual((date.fromisoformat(next_window[1])-date.fromisoformat(next_window[0])).days,90)
        seen=[]
        def client(issuer,max_pages,research_window):
            seen.append((issuer,research_window))
            return []
        r=discover(ledger(),3,client,today=date(2026,10,26))
        self.assertEqual(r["window_cycle"],1)
        self.assertEqual(r["attempted"],3)
        self.assertTrue(any(date.fromisoformat(w[0])>date(2025,11,4)
                            for _,w in seen))
        self.assertFalse(r["historical_PIT_verified"])
        self.assertEqual(r["trade_gate"],"BLOCKED")

    def test_recent_source_clamps_to_today_and_wraps_without_future_dates(self):
        for cycle in (0,1,10000):
            window,segment,total=window_for_halt(date(2026,10,20),date(2026,10,26),cycle)
            self.assertEqual(segment,0)
            self.assertEqual(total,1)
            self.assertEqual(window,("2026-10-19","2026-10-26"))
        with self.assertRaises(ValueError):
            window_for_halt(date(2026,11,1),date(2026,10,26),0)
        with self.assertRaises(ValueError):
            window_for_halt(date(2026,10,1),date(2026,10,26),-1)

    def test_research_window_never_extends_unbounded(self):
        r=discover(ledger(),1,lambda *a,**kw:[],today=date(2026,10,26))
        for item in r["selected_halt_sources"]:
            start=date.fromisoformat(item["search_window_start"])
            end=date.fromisoformat(item["search_window_end"])
            self.assertLessEqual((end-start).days,91)
    def test_prior_archive_skips_already_paired_and_rotates_remaining(self):
        q=ledger()
        paired_issuer=q["official_resumption_followups"][0]
        pair={"issuer":paired_issuer["issuer"],
              "halt_original_sha256":paired_issuer["original_pdf_sha256"],
              "historical_first_publication_verified":False,
              "official_resume_effective_date_verified":False,
              "whole_interval_tradability_verified":False}
        other=[{"issuer":r["issuer"],
                "halt_original_sha256":r["original_pdf_sha256"],
                "status":"NO_RESUME_PAIR_IN_LIMITED_ARCHIVE_NOT_PROOF_OF_CONTINUING_HALT"}
               for r in q["official_resumption_followups"][1:]]
        archive={"phase":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
                 "trade_gate":"BLOCKED","historical_PIT_verified":False,
                 "official_halt_resume_intervals_certified":0,
                 "authenticated_first_publication_count":0,
                 "text_only_halt_resume_pairs":[pair],
                 "deduplicated_research_text_pairs":1,
                 "unpaired_original_halt_followups":other,
                 "unpaired_halt_sources_remaining_in_bounded_research":len(other)}
        first=targets(q,1,today=date(2026,10,26),paired=archive)
        second=targets(q,2,today=date(2026,10,26),paired=archive)
        self.assertEqual(len(first+second),5)
        self.assertNotIn(paired_issuer["issuer"],{r["issuer"] for r in first+second})
        report=discover(q,1,lambda *a,**kw:[],today=date(2026,10,26),paired=archive)
        self.assertEqual(report["archive_remaining_unpaired_count"],5)
        self.assertEqual(report["trade_gate"],"BLOCKED")
        archive["unpaired_original_halt_followups"].append(other[0])
        with self.assertRaises(ValueError):
            targets(q,1,today=date(2026,10,26),paired=archive)

    def test_archive_evidence_cannot_exclude_unknown_source(self):
        q=ledger()
        archive={"phase":"P3_HALT_RESUME_ORIGINAL_SHA_RESEARCH_PAIRS",
                 "trade_gate":"BLOCKED","historical_PIT_verified":False,
                 "official_halt_resume_intervals_certified":0,
                 "authenticated_first_publication_count":0,
                 "text_only_halt_resume_pairs":[],
                 "deduplicated_research_text_pairs":0,
                 "unpaired_original_halt_followups":[
                     {"issuer":"sh.600000","halt_original_sha256":"b"*64,
                      "status":"NO_RESUME_PAIR_IN_LIMITED_ARCHIVE_NOT_PROOF_OF_CONTINUING_HALT"}],
                 "unpaired_halt_sources_remaining_in_bounded_research":1}
        with self.assertRaises(ValueError):
            targets(q,1,today=date(2026,10,26),paired=archive)
    def test_empty_missing_halt_queue_fails(self):
        q=ledger();q["official_resumption_followups"]=[];q["unpaired_halt_starts_needing_resumption_search"]=0
        with self.assertRaises(ValueError):discover(q,1,lambda *a,**kw:[],today=date(2026,10,26))
if __name__=="__main__":unittest.main()
