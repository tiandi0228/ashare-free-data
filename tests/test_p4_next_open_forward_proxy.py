"""Next observed open price is never a verified broker fill."""
import json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
from collector.p4_next_open_forward_proxy import observe

def fixture(base,mode="normal"):
    root=Path(base)/"archive"; shard=root/"epoch"/"shard_0000";shard.mkdir(parents=True)
    code="sh.600000"
    values=[("2026-01-05","10","10","1"),
            ("2026-01-06","11","11","1"),
            ("2026-01-07","11","11","1"),
            ("2026-01-08","12","12","1")]
    if mode=="censored":values=values[:3]
    if mode=="blocked":values[-1]=(values[-1][0],"12","12","0")
    rows=["date,code,open,high,low,close,volume,amount,adjustflag,tradestatus"]
    for day,op,close,status in values:
        rows.append(f"{day},{code},{op},{max(float(op),float(close))},{min(float(op),float(close))},{close},100,1000,3,{status}")
    raw=("\n".join(rows)+"\n").encode()
    (shard/"sh_600000.csv").write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest()
    (shard/"quality.json").write_text(json.dumps({"results":[{"code":code,"sha256":sha}]}))
    manifest=Path(base)/"manifest.json"
    manifest.write_text(json.dumps({
        "archive_commit_sha":"a"*40,
        "cutoff_inclusive":"2025-12-31",
        "nonoverlapping_event_evidence":[{
            "issuer":code,"signal_completed_date":"2026-01-05",
            "source_csv_sha256":sha}]}))
    return root,manifest

class NextOpenProxyTests(unittest.TestCase):
    @patch("collector.p4_next_open_forward_proxy.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_next_open_not_signal_close_and_no_fills(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,m=fixture(d)
            r=observe(root,m)
            self.assertEqual(r["status"],"OBSERVED_NEXT_OPEN_PROXY_NOT_BACKTEST")
            self.assertEqual(r["positive_price_changes"],1)
            self.assertEqual(r["observed_next_open_to_third_close"],1)
            row=r["observed_price_pairs"][0]
            self.assertEqual(row["overnight_open_gap_pct"],"10.0000")
            self.assertEqual(row["next_open_to_third_close_change_pct"],"9.0909")
            self.assertFalse(row["next_open_fill_assumed"])
            self.assertFalse(row["exit_close_fill_assumed"])
            self.assertIsNone(row["trade_return"])
            self.assertFalse(r["historical_OOS_validated"])
            self.assertEqual(r["trade_gate"],"BLOCKED")
            verified.assert_called_once()
    @patch("collector.p4_next_open_forward_proxy.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_censored_event_not_zero_price_change(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,m=fixture(d,"censored")
            r=observe(root,m)
            self.assertEqual(r["censored_events"],1)
            self.assertEqual(r["observed_next_open_to_third_close"],0)
            self.assertIsNone(r["positive_observation_share_pct"])
    @patch("collector.p4_next_open_forward_proxy.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_vendor_status_blocks_outcome(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,m=fixture(d,"blocked")
            r=observe(root,m)
            self.assertEqual(r["future_vendor_status_blocked"],1)
            self.assertEqual(r["observed_price_pairs"],[])
    @patch("collector.p4_next_open_forward_proxy.verify",return_value={"trade_gate":"BLOCKED","orders":[]})
    def test_tampered_csv_refused(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,m=fixture(d)
            (root/"epoch"/"shard_0000"/"sh_600000.csv").write_text("tampered")
            self.assertEqual(observe(root,m)["reason"],"ORIGINAL_CSV_SHA_MISMATCH")
    def test_manifest_must_have_immutable_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root,m=fixture(d)
            z=json.loads(m.read_text());z["archive_commit_sha"]=None
            m.write_text(json.dumps(z))
            self.assertEqual(observe(root,m)["reason"],"UNPINNED_ARCHIVE")
    @patch("collector.p4_next_open_forward_proxy.verify",return_value={"trade_gate":"OPEN","orders":[1]})
    def test_unsafe_event_verification_blocks(self,verified):
        with tempfile.TemporaryDirectory() as d:
            root,m=fixture(d)
            self.assertEqual(observe(root,m)["reason"],"UNSAFE_INDEPENDENT_EVENT_AUDIT")
if __name__=="__main__":unittest.main()
