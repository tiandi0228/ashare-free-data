"""Bounded future-known vendor early-only coverage cannot become PIT membership."""
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from collector.p1_early_only_recovery import capture, choose_originals


def synthetic_vendor_rosters():
    common={f"sh.{600000+i:06d}" for i in range(3150)}
    common.remove("sh.600421")
    early_only={"sh.600421"} | {f"sh.{604000+i:06d}" for i in range(31)}
    late_only={f"sh.{604100+i:06d}" for i in range(46)}
    assert len(common)==3149 and len(early_only)==32 and len(late_only)==46
    return sorted(common|early_only),sorted(common|late_only)


def csv_content(codes):
    output=io.StringIO(newline="")
    writer=csv.writer(output,lineterminator="\n")
    writer.writerow(("code","tradeStatus","code_name"))
    for code in codes:
        writer.writerow((code,"1","SYNTHETIC_ISSUER"))
    return output.getvalue()


def fake_audit(_):
    return {
        "status":"ORIGINAL_TWO_VENDOR_ROSTERS_REPLAYED_PIT_BLOCKED",
        "original_vendor_capture_run":39613467121,
        "issuer_pool_size_2025_05_26":3181,
        "issuer_pool_size_2026_10_20":3195,
        "official_exchange_mainboard_membership_verified":False,
        "trade_gate":"BLOCKED",
        "date_results":[
            {"full_original_sha256":"a"*64},
            {"full_original_sha256":"b"*64},
        ],
    }


def fake_manifest(path):
    if "delisted" in str(path):
        return (["sh.600421"]+[f"sh.{605000+i:06d}" for i in range(7)],"2"*64)
    return ([f"sz.{i:06d}" for i in range(1,17)],"1"*64)


def bar(code):
    return [["2025-05-26",code,"10","10","10","10","100","1000","3","1"]]


class MockReply:
    error_code="0"
    fields="date,code,open,high,low,close,volume,amount,adjustflag,tradestatus".split(",")
    def __init__(self,code):
        self.rows=bar(code);self.i=0
    def next(self):
        if self.i>=len(self.rows):return False
        self.i+=1;return True
    def get_row_data(self):
        return self.rows[self.i-1]


class Provider:
    def __init__(self,failed_code=None,login_fail=False):
        self.failed_code=failed_code
        self.login_fail=login_fail
        self.queried=[];self.logouts=0
    def login(self):
        return type("R",(),{"error_code":"9" if self.login_fail else "0"})()
    def logout(self):
        self.logouts+=1
    def query_history_k_data_plus(self,code,**kwargs):
        self.queried.append((code,kwargs))
        result=MockReply(code)
        if code==self.failed_code:result.error_code="1"
        return result


class EarlyOnlyTests(unittest.TestCase):
    def test_select_eight_lex_first_from_validated_dated_originals(self):
        early,late=synthetic_vendor_rosters()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp,"rosters.zip")
            with ZipFile(p,"w") as z:
                z.writestr("mainboard_prefix_2025-05-26.csv",csv_content(early))
                z.writestr("mainboard_prefix_2026-10-20.csv",csv_content(late))
            with patch("collector.p1_early_only_recovery.audit_archive",side_effect=fake_audit), \
                 patch("collector.p1_early_only_recovery.manifest",side_effect=fake_manifest):
                selected,trace=choose_originals(p,"a","delisted")
        self.assertEqual(selected,[f"sh.{604000+i:06d}" for i in range(8)])
        self.assertEqual(trace["early_only_vendor_issuer_count"],32)
        self.assertEqual(trace["early_only_excluding_prior_24_count"],31)
        self.assertTrue(trace["not_a_historical_asof_eligible_universe"])
        self.assertTrue(trace["not_independent_exchange_delisting_proof"])

    def test_prechecked_source_receipt_refuses_false_pit(self):
        early,late=synthetic_vendor_rosters()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp,"rosters.zip")
            with ZipFile(p,"w") as z:
                z.writestr("mainboard_prefix_2025-05-26.csv",csv_content(early))
                z.writestr("mainboard_prefix_2026-10-20.csv",csv_content(late))
            bad=fake_audit(None)
            bad["official_exchange_mainboard_membership_verified"]=True
            with patch("collector.p1_early_only_recovery.audit_archive",return_value=bad):
                with self.assertRaisesRegex(ValueError,"not eligible"):
                    choose_originals(p,"a","delisted")

    def test_eight_free_issuer_queries_only_research(self):
        codes=[f"sh.{604000+i:06d}" for i in range(8)]
        client=Provider()
        r=capture(client,codes,{"source_run_id":39613467121,
            "not_a_historical_asof_eligible_universe":True})
        self.assertEqual(r["status"],
                         "EIGHT_HISTORICAL_EARLY_ONLY_VENDOR_SAMPLES_OBSERVED_PIT_BLOCKED")
        self.assertEqual(r["logical_source_queries"],8)
        self.assertEqual(r["source_observed_issuers"],8)
        self.assertEqual(len(client.queried),8)
        self.assertEqual(client.logouts,1)
        self.assertTrue(all(len(x["original_source_sha256"])==64 for x in r["results"]))
        self.assertFalse(r["source_raw_bar_bytes_published"])
        self.assertFalse(r["official_historical_PIT_universe_verified"])
        self.assertFalse(r["valid_for_backtest_membership_asof_early_day"])
        self.assertEqual(r["trade_gate"],"BLOCKED")
        self.assertEqual(r["orders"],[])

    def test_one_broken_issuer_blocks_cohort(self):
        codes=[f"sh.{604000+i:06d}" for i in range(8)]
        r=capture(Provider(failed_code=codes[3]),codes,{
            "source_run_id":39613467121,
            "not_a_historical_asof_eligible_universe":True})
        self.assertEqual(r["status"],"BLOCKED_PARTIAL")
        self.assertEqual(r["source_observed_issuers"],7)
        self.assertEqual(r["source_observed_rows"],7)
        self.assertEqual(r["results"][3]["status"],"SOURCE_ERROR")

    def test_unavailable_login_never_forges_issuer_data(self):
        codes=[f"sh.{604000+i:06d}" for i in range(8)]
        provider=Provider(login_fail=True)
        r=capture(provider,codes,{
            "source_run_id":39613467121,
            "not_a_historical_asof_eligible_universe":True})
        self.assertEqual(r["status"],"BLOCKED_PARTIAL")
        self.assertEqual(r["logical_source_queries"],0)
        self.assertEqual(r["source_observed_issuers"],0)
        self.assertEqual(provider.queried,[])
        self.assertEqual(r["orders"],[])

    def test_reject_unbounded_basket_before_login(self):
        with self.assertRaisesRegex(ValueError,"invalid"):
            capture(Provider(),["sh.604000"]*8,{
                "source_run_id":39613467121,
                "not_a_historical_asof_eligible_universe":True})


if __name__=="__main__":
    unittest.main()
