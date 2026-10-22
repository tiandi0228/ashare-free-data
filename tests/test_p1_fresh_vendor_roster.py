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
        return Result([[f"sh.{600000+i}","1",f"issuer{i}"] for i in range(1000)] if self.valid else [])

class FreshRosterTests(unittest.TestCase):
    def test_fresh_roster_observed_but_not_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider=Provider()
            self.assertEqual(capture(tmp,provider,"2026-10-22"),0)
            q=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(q["mainboard_prefix_rows"],1000)
            self.assertEqual(q["logical_queries"],1)
            self.assertFalse(q["historical_PIT_verified"])
            self.assertFalse(q["publisher_authenticated"])
            self.assertEqual(q["trade_gate"],"BLOCKED")
            self.assertEqual(provider.queries,1)
    def test_one_retry_recovers_truncated_roster(self):
        class TruncatedOnce(Provider):
            def query_all_stock(self,day):
                self.queries+=1
                count=50 if self.queries==1 else 1000
                return Result([[f"sh.{600000+i}","1",f"issuer{i}"] for i in range(count)])
        with tempfile.TemporaryDirectory() as tmp:
            api=TruncatedOnce()
            self.assertEqual(capture(tmp,api,"2026-10-22"),0)
            q=json.loads((Path(tmp)/"quality.json").read_text())
            self.assertEqual(q["logical_queries"],2)
            self.assertEqual(q["mainboard_prefix_rows"],1000)
            self.assertEqual(q["trade_gate"],"BLOCKED")
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
