import json,tempfile,unittest,hashlib
from datetime import date,timedelta
from pathlib import Path
from collector.p4_independent_event_evidence import verify

class IndependentEvents(unittest.TestCase):
    def test_roundtrip_and_hash_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"epoch"/"shard_0000";folder.mkdir(parents=True)
            dates=[(date(2025,12,16)+timedelta(days=i)).isoformat() for i in range(25)]
            rows=["date,tradestatus,close"]+[f"{day},1,{11 if i==20 else 10}" for i,day in enumerate(dates)]
            raw=("\n".join(rows)+"\n").encode()
            digest=hashlib.sha256(raw).hexdigest()
            (folder/"sh_600000.csv").write_bytes(raw)
            (folder/"quality.json").write_text(json.dumps({"results":[{"code":"sh.600000","sha256":digest}]}))
            report={"trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
                    "returns_computed":False,"historical_OOS_validated":False,
                    "nonoverlapping_three_observation_crossing_events":1,
                    "nonoverlapping_crossings_with_three_following_vendor_tradable_rows":1,
                    "nonoverlapping_event_evidence":[{"issuer":"sh.600000","source_csv_sha256":digest,
                        "signal_completed_date":dates[20],
                        "three_future_observed_dates":dates[21:24],
                        "three_future_vendor_tradable":True,"fill_assumed":False}]}
            path=root/"manifest.json";path.write_text(json.dumps(report))
            self.assertEqual(verify(root,path)["independently_verified_events"],1)
            report["nonoverlapping_event_evidence"][0]["signal_completed_date"]=dates[21]
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"MA20 crossing"):verify(root,path)
            report["nonoverlapping_event_evidence"][0]["signal_completed_date"]=dates[20]
            report["nonoverlapping_event_evidence"][0]["source_csv_sha256"]="0"*64
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,"source SHA mismatch"):verify(root,path)
if __name__=="__main__":unittest.main()
