import json,tempfile,unittest,hashlib
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from collector.p4_independent_event_evidence import verify
from collector.p4_real_ma20_forward_observation import audit

class IndependentEvents(unittest.TestCase):
    def test_roundtrip_and_hash_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"epoch"/"shard_0000";folder.mkdir(parents=True)
            dates=[(date(2025,12,16)+timedelta(days=i)).isoformat() for i in range(25)]
            rows=["date,tradestatus,close"]+[f"{day},1,{11 if i==20 else 10}" for i,day in enumerate(dates)]
            raw=bytes([10]).join(x.encode() for x in rows)+bytes([10])
            digest=hashlib.sha256(raw).hexdigest()
            (folder/"sh_600000.csv").write_bytes(raw)
            (folder/"quality.json").write_text(json.dumps({"results":[{"code":"sh.600000","sha256":digest}]}))
            report={"cutoff_inclusive":"2025-12-31","trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
                    "returns_computed":False,"historical_OOS_validated":False,
                    "nonoverlapping_three_observation_crossing_events":1,
                    "nonoverlapping_crossings_with_three_following_vendor_tradable_rows":1,
                    "nonoverlapping_event_evidence":[{"issuer":"sh.600000","source_csv_sha256":digest,
                        "signal_completed_date":dates[20],
                        "three_future_observed_dates":dates[21:24],
                        "three_future_vendor_tradable":True,"fill_assumed":False}]}
            path=root/"manifest.json";path.write_text(json.dumps(report))
            with patch("collector.p4_independent_event_evidence.assess",return_value={"details":[{"code":"sh.600000"}]}):
                self.assertEqual(verify(root,path)["independently_verified_events"],1)
            report["cutoff_inclusive"]="2026-01-15"
            path.write_text(json.dumps(report))
            with patch("collector.p4_independent_event_evidence.assess",return_value={"details":[{"code":"sh.600000"}]}):
                with self.assertRaisesRegex(ValueError,"training holdout boundary"):verify(root,path)
            report["cutoff_inclusive"]="2025-12-31"
            report["nonoverlapping_event_evidence"][0]["signal_completed_date"]=dates[21]
            path.write_text(json.dumps(report))
            with patch("collector.p4_independent_event_evidence.assess",return_value={"details":[{"code":"sh.600000"}]}):
                with self.assertRaisesRegex(ValueError,"MA20 crossing"):verify(root,path)
            report["nonoverlapping_event_evidence"][0]["signal_completed_date"]=dates[20]
            report["nonoverlapping_event_evidence"][0]["source_csv_sha256"]="0"*64
            path.write_text(json.dumps(report))
            with patch("collector.p4_independent_event_evidence.assess",return_value={"details":[{"code":"sh.600000"}]}):
                with self.assertRaisesRegex(ValueError,"source SHA mismatch"):verify(root,path)

    def test_full_inventory_replay_rejects_silently_dropped_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"epoch"/"shard_0000"
            folder.mkdir(parents=True)
            dates=[]
            day=date(2025,12,1)
            while len(dates)<70:
                if day.weekday()<5:
                    dates.append(day.isoformat())
                day+=timedelta(days=1)
            # Three well-separated real MA20 crossings after the cutoff.
            closes=[10]*20+[13]+[9]*10+[13]+[9]*11+[13]+[9]*26
            self.assertEqual(len(closes),70)
            rows=["date,tradestatus,close"]+[
                f"{d},1,{px}" for d,px in zip(dates,closes)]
            raw=bytes([10]).join(x.encode() for x in rows)+bytes([10])
            digest=hashlib.sha256(raw).hexdigest()
            (folder/"sh_600000.csv").write_bytes(raw)
            (folder/"quality.json").write_text("{}")
            mock_receipt={"details":[{"code":"sh.600000"}]}
            with (patch("collector.p4_real_ma20_forward_observation.assess",
                        return_value=mock_receipt),
                  patch("collector.p4_independent_event_evidence.assess",
                        return_value=mock_receipt)):
                manifest=audit(root,cutoff="2025-12-10")
                self.assertGreaterEqual(
                    manifest["nonoverlapping_three_observation_crossing_events"],2)
                manifest_path=root/"manifest.json"
                manifest_path.write_text(json.dumps(manifest))
                result=verify(root,manifest_path)
                self.assertEqual(
                    result["independently_verified_events"],
                    manifest["nonoverlapping_three_observation_crossing_events"])

                # A forged report could drop an event and rewrite both counters.
                # The old verifier accepted this; complete replay must not.
                manifest["nonoverlapping_event_evidence"].pop(0)
                manifest["nonoverlapping_three_observation_crossing_events"]=len(
                    manifest["nonoverlapping_event_evidence"])
                manifest["nonoverlapping_crossings_with_three_following_vendor_tradable_rows"]=sum(
                    x["three_future_vendor_tradable"]
                    for x in manifest["nonoverlapping_event_evidence"])
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(
                    ValueError,"incomplete or altered MA20 event"):
                    verify(root,manifest_path)

if __name__=="__main__":unittest.main()
