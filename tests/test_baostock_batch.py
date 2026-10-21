import json,tempfile,unittest
from pathlib import Path
from collector.baostock_batch import manifest,run

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
