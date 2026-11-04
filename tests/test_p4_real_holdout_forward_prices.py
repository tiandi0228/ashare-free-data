"""Three *observed* later vendor closes never become pretend broker fills."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from collector.p4_real_holdout_forward_prices import observe

COMMIT="a"*40
def fixture(tmp,kind="positive"):
    root=Path(tmp)/"archive"
    folder=root/"epoch"/"shard_0000"
    folder.mkdir(parents=True)
    code="sh.600000"
    prices=[10,10.2,10.3,11.0]
    if kind=="negative":prices[-1]=9.0
    if kind=="zero":prices[-1]=10.0
    bars=[f"2026-01-0{i+5},{code},{p},{p},{p},{p},100,1000,3,1"
          for i,p in enumerate(prices)]
    if kind=="censored":bars=bars[:3]
    if kind=="suspended":bars[-1]=bars[-1].rsplit(",",1)[0]+",0"
    raw=("date,code,open,high,low,close,volume,amount,adjustflag,tradestatus\n"+
         "\n".join(bars)+"\n").encode()
    (folder/"sh_600000.csv").write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    (folder/"quality.json").write_text(json.dumps({"results":[{"code":code,"sha256":digest}]}))
    days=[line[:10] for line in bars]
    event={"issuer":code,"source_csv_sha256":digest,
           "signal_completed_date":days[0],
           "three_future_observed_dates":days[1:],
           "three_future_vendor_tradable":kind not in ("censored","suspended"),
           "fill_assumed":False}
    manifest=Path(tmp)/"manifest.json"
    manifest.write_text(json.dumps({
        "cutoff_inclusive":"2025-12-31","archive_commit_sha":COMMIT,
        "nonoverlapping_event_evidence":[event]}))
    return root,manifest,event

class HoldoutPriceTests(unittest.TestCase):
    @patch("collector.p4_real_holdout_forward_prices.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_positive_close_change_is_not_a_filled_trade(self,mock):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t)
            result=observe(root,manifest)
            self.assertEqual(result["status"],"HOLDOUT_PRICE_OBSERVATIONS_NOT_BACKTEST")
            self.assertEqual(result["observed_with_three_vendor_tradable_rows"],1)
            self.assertEqual(result["observed_positive_close_changes"],1)
            item=result["research_observations"][0]
            self.assertEqual(item["close_to_third_later_close_change_pct"],"10.0000")
            self.assertIsNone(item["trade_return"])
            self.assertFalse(item["entry_filled"])
            self.assertFalse(result["strategy_backtest_certified"])
            self.assertFalse(result["historical_OOS_validated"])
            self.assertEqual(result["trade_gate"],"BLOCKED")
            self.assertEqual(result["orders"],[])
            mock.assert_called_once()
    @patch("collector.p4_real_holdout_forward_prices.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_negative_price_outcome_not_auto_claimed_strategy_loss(self,mock):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t,"negative")
            r=observe(root,manifest)
            self.assertEqual(r["observed_negative_close_changes"],1)
            self.assertEqual(r["research_observations"][0]["close_to_third_later_close_change_pct"],"-10.0000")
            self.assertFalse(r["returns_computed_as_trades"])
    @patch("collector.p4_real_holdout_forward_prices.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_short_horizon_is_censored_not_zero_return(self,mock):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t,"censored")
            r=observe(root,manifest)
            self.assertEqual(r["censored_insufficient_following_rows"],1)
            self.assertEqual(r["observed_with_three_vendor_tradable_rows"],0)
            self.assertEqual(r["research_observations"],[])
    @patch("collector.p4_real_holdout_forward_prices.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_future_suspension_excluded(self,mock):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t,"suspended")
            r=observe(root,manifest)
            self.assertEqual(r["unscorable_future_vendor_status"],1)
            self.assertEqual(r["observed_with_three_vendor_tradable_rows"],0)
    @patch("collector.p4_real_holdout_forward_prices.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_source_tamper_rejected(self,mock):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t)
            (root/"epoch"/"shard_0000"/"sh_600000.csv").write_text("malicious")
            r=observe(root,manifest)
            self.assertEqual(r["status"],"REJECTED")
            self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_unpinned_archive_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t)
            data=json.loads(manifest.read_text());data["archive_commit_sha"]=None
            manifest.write_text(json.dumps(data))
            self.assertEqual(observe(root,manifest)["reason"],"MISSING_PINNED_ARCHIVE_COMMIT")
    @patch("collector.p4_real_holdout_forward_prices.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_future_date_cannot_be_training_period(self,mock):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t)
            data=json.loads(manifest.read_text());data["cutoff_inclusive"]="2026-01-05"
            manifest.write_text(json.dumps(data))
            r=observe(root,manifest)
            self.assertEqual(r["reason"],"TRAIN_PERIOD_LEAKAGE")
    @patch("collector.p4_real_holdout_forward_prices.verify",return_value={"trade_gate":"OPEN","orders":[1]})
    def test_independent_gate_must_be_closed(self,mock):
        with tempfile.TemporaryDirectory() as t:
            root,manifest,event=fixture(t)
            self.assertEqual(observe(root,manifest)["reason"],"UNSAFE_INDEPENDENT_EVENT_REPLAY")
if __name__=="__main__":unittest.main()
