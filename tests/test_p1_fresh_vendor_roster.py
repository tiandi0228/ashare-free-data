import json
import tempfile
import unittest
from pathlib import Path
from collector.p1_fresh_vendor_roster import capture

class Result:
    error_code="0"
    fields=["code","tradeStatus","code_name"]
    def __init__(self,rows):
        self.rows=iter(rows)
        self.current=None
    def next(self):
        self.current=next(self.rows,None)
        return self.current is not None
    def get_row_data(self):
        return self.current

class Provider:
    def __init__(self,valid=True):
        self.valid=valid
        self.queries=0
    def login(self):
        return Result([])
    def logout(self):
        pass
    def query_all_stock(self,day):
        self.queries+=1
        return Result([[f"sh.{[600,601,603][i//1000]*1000+i%1000}","1",f"issuer{i}"] for i in range(3000)] if self.valid else [])

class FreshRosterTests(unittest.TestCase):
    def test_fresh_roster_observed_but_not_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider=Provider()
            self.assertEqual(capture(tmp,provider,"2026-10-22"),0)
            q=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(q["mainboard_prefix_rows"],3000)
            self.assertEqual(q["logical_queries"],1)
            self.assertFalse(q["historical_PIT_verified"])
            self.assertFalse(q["publisher_authenticated"])
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertEqual(provider.queries,1)
    def test_one_retry_recovers_truncated_roster(self):
        class TruncatedOnce(Provider):
            def query_all_stock(self,day):
                self.queries+=1
                count=50 if self.queries==1 else 3000
                return Result([[f"sh.{[600,601,603][i//1000]*1000+i%1000}","1",f"issuer{i}"] for i in range(count)])
        with tempfile.TemporaryDirectory() as tmp:
            api=TruncatedOnce()
            self.assertEqual(capture(tmp,api,"2026-10-22"),0)
            q=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(q["logical_queries"],2)
            self.assertEqual(q["mainboard_prefix_rows"],3000)
            self.assertEqual(q["trade_gate"],"BLOCKED")
    def test_transient_login_error_recovers_with_bounded_retry(self):
        class LoginTransient(Provider):
            def __init__(self):
                super().__init__()
                self.logins=0
            def login(self):
                self.logins+=1
                if self.logins==1:
                    item=Result([])
                    item.error_code="10001"
                    return item
                return Result([])
        with tempfile.TemporaryDirectory() as tmp:
            api=LoginTransient()
            self.assertEqual(capture(tmp,api,"2026-10-22"),0)
            quality=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(quality["login_attempts"],2)
            self.assertEqual(api.logins,2)
            self.assertEqual(quality["trade_gate"],"BLOCKED")

    def test_repeated_login_failure_blocks_without_roster_query(self):
        class LoginAlwaysFails(Provider):
            def login(self):
                self.logins+=1
                item=Result([])
                item.error_code="10001"
                return item
        with tempfile.TemporaryDirectory() as tmp:
            api=LoginAlwaysFails()
            api.logins=0
            self.assertEqual(capture(tmp,api,"2026-10-22"),2)
            quality=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(quality["login_attempts"],2)
            self.assertEqual(quality["last_login_error_code"],"10001")
            self.assertEqual(api.queries,0)
            self.assertEqual(quality["status"],"BLOCKED_PARTIAL")
            self.assertFalse((Path(tmp)/"mainboard.csv").exists())

    def test_one_retry_recovers_transient_vendor_error(self):
        class ErrorResult:
            error_code="10001"
            fields=["code","tradeStatus","code_name"]
        class TransientOnce(Provider):
            def query_all_stock(self,day):
                self.queries+=1
                if self.queries==1:
                    return ErrorResult()
                return Result([[f"sh.{[600,601,603][i//1000]*1000+i%1000}","1",f"issuer{i}"] for i in range(3000)])
        with tempfile.TemporaryDirectory() as tmp:
            api=TransientOnce()
            self.assertEqual(capture(tmp,api,"2026-10-22"),0)
            receipt=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(receipt["logical_queries"],2)
            self.assertEqual(receipt["mainboard_prefix_rows"],3000)
            self.assertEqual(receipt["trade_gate"],"BLOCKED")

    def test_two_vendor_errors_fail_closed(self):
        class ErrorResult:
            error_code="10001"
            fields=["code","tradeStatus","code_name"]
        class AlwaysError(Provider):
            def query_all_stock(self,day):
                self.queries+=1
                return ErrorResult()
        with tempfile.TemporaryDirectory() as tmp:
            api=AlwaysError()
            self.assertEqual(capture(tmp,api,"2026-10-22"),2)
            receipt=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(receipt["logical_queries"],2)
            self.assertEqual(receipt["status"],"BLOCKED_PARTIAL")
            self.assertEqual(receipt["last_source_error_code"],"10001")
            self.assertFalse((Path(tmp)/"mainboard.csv").exists())

    def test_failed_capture_does_not_leave_stale_roster_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"mainboard.csv").write_text("stale,not,current\n")
            self.assertEqual(capture(tmp,Provider(False),"2026-10-22"),2)
            self.assertFalse((folder/"mainboard.csv").exists())
            quality=json.loads((folder/"quality.json").read_text())
            self.assertEqual(quality["status"],"BLOCKED_PARTIAL")
            self.assertEqual(quality["trade_gate"],"BLOCKED")

    def test_implausibly_small_roster_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(capture(tmp,Provider(False),"2026-10-22"),2)
            q=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(q["status"],"BLOCKED_PARTIAL")
            self.assertEqual(q["logical_queries"],2)
            self.assertEqual(q["last_source_total_rows"],0)
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertFalse((Path(tmp)/"mainboard.csv").exists())
if __name__=="__main__":unittest.main()
