import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from collector.p4_real_ma20_forward_observation import audit

class ForwardObservationTests(unittest.TestCase):
    def test_no_archive(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):audit(root)

    def test_vendor_forward_only_never_fills(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"batch"/"shard_0000";folder.mkdir(parents=True)
            (folder/"quality.json").write_text("{}")
            rows=["date,code,open,high,low,close,volume,amount,adjustflag,tradestatus"]
            from datetime import date,timedelta
            start=date(2025,12,1)
            for i in range(40):
                d=(start+timedelta(days=i)).isoformat()
                px=10+i/10
                rows.append(f"{d},sh.600000,{px},{px},{px},{px},100,1000,3,{0 if i==35 else 1}")
            (folder/"sh_600000.csv").write_text("\n".join(rows)+"\n")
            with patch("collector.p4_real_ma20_forward_observation.assess",return_value={"details":[{"code":"sh.600000"}]}):
                result=audit(tmp,"2025-12-20")
            self.assertGreater(result["post_cutoff_ma20_observations"],0)
            self.assertLessEqual(result["fresh_ma20_crossing_events"],result["post_cutoff_ma20_observations"])
            self.assertLessEqual(result["fresh_crossing_events_with_three_following_vendor_tradable_rows"],result["fresh_ma20_crossing_events"])
            self.assertLess(result["three_following_vendor_tradable_rows"],result["post_cutoff_ma20_observations"])
            self.assertEqual(result["post_cutoff_ma20_observations"],result["three_following_vendor_tradable_rows"]+result["observations_censored_at_archive_end"]+result["observations_blocked_by_vendor_status"])
            self.assertEqual(result["issuers_with_ma20_observations"],1)
            self.assertEqual(result["issuers_with_three_following_vendor_tradable_rows"],1)
            self.assertFalse(result["returns_computed"])
            self.assertEqual(result["trade_gate"],"BLOCKED")

if __name__=="__main__":unittest.main()
