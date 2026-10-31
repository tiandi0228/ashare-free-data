import json,tempfile,unittest
from pathlib import Path
from collector.baostock_batch import manifest,run,check_daily_bars

class Result:
    error_code="0"
    fields="date,code,open,high,low,close,volume,amount,adjustflag,tradestatus".split(",")
    def __init__(self,code):self.code=code;self.i=0
    def next(self):
        self.i+=1
        return self.i<=2
    def get_row_data(self):
        return ["2024-10-2"+str(self.i),self.code,"1","1","1","1","1","1","3","1"]
class Client:
    def __init__(self):self.calls=[];self.out=False
    def login(self):return type("Auth",(),{"error_code":"0"})()
    def logout(self):self.out=True
    def query_history_k_data_plus(self,code,**kwargs):
        self.calls.append(code)
        return Result(code)
class Tests(unittest.TestCase):
    def test_two_issuer_capture(self):
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\nsz.000001\n")
            api=Client()
            self.assertEqual(run(m,0,Path(d)/"o",api),0)
            q=json.loads((Path(d)/"o/quality.json").read_text())
            self.assertEqual(q["status"],"OBSERVED_SUBSET_UNVERIFIED")
            self.assertEqual(q["query_attempts"],2)
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertFalse(q["full_market_history_verified"])
            self.assertEqual(len(api.calls),2)
            self.assertTrue(api.out)
    def test_one_provider_timeout_retries_once_with_full_history(self):
        class Flaky(Client):
            def query_history_k_data_plus(self,code,**kwargs):
                self.calls.append(code)
                if len(self.calls)==1:raise TimeoutError("transient")
                return Result(code)
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            source=Flaky()
            self.assertEqual(run(m,0,Path(d)/"out",source),0)
            report=json.loads((Path(d)/"out/quality.json").read_text())
            self.assertEqual(report["query_attempts"],1)
            self.assertEqual(report["provider_attempts"],2)
            self.assertEqual(report["transient_retries"],1)
            self.assertEqual(report["results"][0]["rows"],2)
            self.assertEqual(report["results"][0]["provider_attempts"],2)
            self.assertEqual(report["trade_gate"],"BLOCKED")
            self.assertEqual(len(source.calls),2)

    def test_stream_break_discards_partial_rows_and_restarts_history(self):
        class Partial(Result):
            def next(self):
                self.i+=1
                if self.i==2:raise ConnectionError("stream disconnected")
                return self.i<=2
        class Flaky(Client):
            def query_history_k_data_plus(self,code,**kwargs):
                self.calls.append(code)
                return Partial(code) if len(self.calls)==1 else Result(code)
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            self.assertEqual(run(m,0,Path(d)/"out",Flaky()),0)
            raw=(Path(d)/"out/sh_600000.csv").read_text()
            self.assertEqual(raw.count("2024-10-21"),1)
            self.assertEqual(raw.count("2024-10-22"),1)
            report=json.loads((Path(d)/"out/quality.json").read_text())
            self.assertEqual(report["provider_attempts"],2)
            self.assertEqual(report["results"][0]["rows"],2)

    def test_repeated_provider_error_blocks_and_retains_no_stale_csv(self):
        class Refused(Client):
            def query_history_k_data_plus(self,code,**kwargs):
                self.calls.append(code)
                answer=Result(code);answer.error_code="10001"
                return answer
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            out=Path(d)/"out";out.mkdir()
            (out/"sh_600000.csv").write_text("stale-source")
            api=Refused()
            self.assertEqual(run(m,0,out,api),2)
            q=json.loads((out/"quality.json").read_text())
            self.assertEqual(q["status"],"BLOCKED_PARTIAL")
            self.assertEqual(q["query_attempts"],1)
            self.assertEqual(q["provider_attempts"],2)
            self.assertEqual(q["transient_retries"],1)
            self.assertEqual(q["results"][0]["failure_category"],"PROVIDER_RESPONSE_INVALID")
            self.assertEqual(q["results"][0]["provider_error_code"],"10001")
            self.assertFalse((out/"sh_600000.csv").exists())
            self.assertEqual(len(api.calls),2)

    def test_malformed_schema_never_retried(self):
        class BadSchema(Client):
            def query_history_k_data_plus(self,code,**kwargs):
                self.calls.append(code)
                result=Result(code);result.fields=["date"]
                return result
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            api=BadSchema()
            self.assertEqual(run(m,0,Path(d)/"out",api),2)
            report=json.loads((Path(d)/"out/quality.json").read_text())
            self.assertEqual(report["provider_attempts"],1)
            self.assertEqual(report["transient_retries"],0)
            self.assertEqual(report["results"][0]["failure_category"],"PROVIDER_SCHEMA_INVALID")
            self.assertEqual(len(api.calls),1)

    def test_impossible_ohlc_never_retried_or_archived(self):
        class BadPrice(Result):
            def get_row_data(self):
                row=super().get_row_data()
                row[3]="0"
                return row
        class BadPriceAPI(Client):
            def query_history_k_data_plus(self,code,**kwargs):
                self.calls.append(code)
                return BadPrice(code)
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            api=BadPriceAPI()
            self.assertEqual(run(m,0,Path(d)/"out",api),2)
            q=json.loads((Path(d)/"out/quality.json").read_text())
            self.assertEqual(q["provider_attempts"],1)
            self.assertEqual(q["transient_retries"],0)
            self.assertEqual(q["results"][0]["status"],"ERROR")
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertFalse((Path(d)/"out/sh_600000.csv").exists())

    def test_login_failure_preserves_provider_code(self):
        class BadLogin(Client):
            def login(self):return type("Auth",(),{"error_code":"10002007"})()
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            api=BadLogin()
            self.assertEqual(run(m,0,Path(d)/"out",api),2)
            q=json.loads((Path(d)/"out/quality.json").read_text())
            self.assertEqual(q["failure_category"],"PROVIDER_LOGIN_REJECTED")
            self.assertEqual(q["provider_login_error_code"],"10002007")
            self.assertEqual(q["query_attempts"],0)
            self.assertEqual(q["trade_gate"],"BLOCKED")

    def test_empty_history_classified_without_fabricating_rows(self):
        class EmptyClient(Client):
            def query_history_k_data_plus(self,code,**kwargs):
                self.calls.append(code)
                r=Result(code)
                r.next=lambda: False
                return r
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            self.assertEqual(run(m,0,Path(d)/"out",EmptyClient()),2)
            q=json.loads((Path(d)/"out/quality.json").read_text())
            self.assertEqual(q["results"][0]["failure_category"],"PROVIDER_EMPTY_HISTORY")
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertFalse((Path(d)/"out/sh_600000.csv").exists())

    def test_reject_impossible_active_prices(self):
        row=["2026-10-20","sh.600000","10","9","8","10","100","1000","3","1"]
        with self.assertRaisesRegex(ValueError,"OHLC"):
            check_daily_bars([row])

    def test_reject_nan_and_non_numeric_active_bar(self):
        for value in ("nan","inf",""):
            with self.subTest(value=value):
                row=["2026-10-20","sh.600000",value,"10","8","9","100","1000","3","1"]
                with self.assertRaises(ValueError):
                    check_daily_bars([row])

    def test_suspended_placeholder_not_counted_as_tradable(self):
        row=["2026-10-20","sh.600000","","","","","","","3","0"]
        self.assertEqual(check_daily_bars([row]),(0,1))

    def test_invalid_manifest_does_not_query(self):
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sz.300001\n")
            with self.assertRaises(ValueError):manifest(m)
    def test_reject_batch_out_of_range(self):
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/"m.txt";m.write_text("sh.600000\n")
            api=Client()
            with self.assertRaises(ValueError):run(m,1,Path(d)/"o",api)
            self.assertEqual(api.calls,[])
if __name__=="__main__":unittest.main()
