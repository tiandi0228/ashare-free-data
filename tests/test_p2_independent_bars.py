import hashlib,json,tempfile,unittest
from pathlib import Path
from collector.p2_independent_bars import assess

class P2IntegrityTests(unittest.TestCase):
    def fixture(self,root):
        raw=b"date,code,open,high,low,close,volume,amount,adjustflag,tradestatus\n2026-01-05,sh.600000,10,11,9,10.5,100,1000,3,1\n2026-01-06,sh.600000,,,,,,,3,0\n"
        (root/"sh_600000.csv").write_bytes(raw)
        receipt={"status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED","orders":[],
                 "historical_point_in_time_universe_verified":False,"issuer_count":1,
                 "results":[{"code":"sh.600000","status":"OBSERVED_UNVERIFIED",
                 "sha256":hashlib.sha256(raw).hexdigest(),"rows":2,"tradable_rows":1,"suspended_status_rows":1}]}
        (root/"quality.json").write_text(json.dumps(receipt))
        return receipt
    def test_real_csv_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            result=assess(root)
            self.assertEqual(result["total_active_rows"],1)
            self.assertEqual(result["vendor_suspended_rows"],1)
            self.assertFalse(result["official_halt_events_verified"])
            self.assertEqual(result["trade_gate"],"BLOCKED")
    def test_source_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            (root/"sh_600000.csv").write_text("tampered")
            with self.assertRaises(ValueError):assess(root)
    def test_false_official_claim_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);receipt=self.fixture(root)
            receipt["historical_point_in_time_universe_verified"]=True
            (root/"quality.json").write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):assess(root)
if __name__=="__main__":unittest.main()
