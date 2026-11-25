"""Archive-backed observations require original receipts, no future rows."""
import hashlib,json,tempfile,unittest
from datetime import date,timedelta
from pathlib import Path
from collector.p2_real_archive_features import observe

def dates(end="2026-11-02",n=21):
    out=[];d=date.fromisoformat(end)
    while len(out)<n:
        if d.weekday()<5:out.append(d.isoformat())
        d-=timedelta(days=1)
    return out[::-1]

def fixture(root,code="sh.600000",last_status="1",future=False):
    folder=Path(root)/"epoch"/"shard_0000"
    folder.mkdir(parents=True)
    values=dates()
    rows=["date,code,open,high,low,close,volume,amount,adjustflag,tradestatus"]
    for i,day in enumerate(values):
        status=last_status if i==len(values)-1 else "1"
        price="10.00" if i<20 else "10.40"
        # Vendor halt records may retain stale OHLC but do not report traded
        # volume/amount; positive turnover alongside status=0 is inconsistent.
        volume,amount=(str(100+i),"1000") if status=="1" else ("","")
        rows.append(f"{day},{code},{price},{price},{price},{price},{volume},{amount},3,{status}")
    if future:
        rows.append(f"2026-11-03,{code},15,15,15,15,200,3000,3,1")
    raw=("\n".join(rows)+"\n").encode()
    (folder/(code.replace(".","_")+".csv")).write_bytes(raw)
    (folder/"quality.json").write_text(json.dumps({
        "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED","orders":[],
        "historical_point_in_time_universe_verified":False,
        "issuer_count":1,"results":[{
           "code":code,"status":"OBSERVED_UNVERIFIED",
           "sha256":hashlib.sha256(raw).hexdigest(),"rows":len(rows)-1,
           "tradable_rows":len(rows)-1 if last_status=="1" else len(rows)-2,
           "suspended_status_rows":0 if last_status=="1" else 1,
        }]}))
    return folder

class RealArchiveFeaturesTests(unittest.TestCase):
    def test_actual_original_csv_yields_not_tradable_research_features(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d)
            r=observe(d,"2026-11-02")
            self.assertEqual(r["status"],"REAL_ARCHIVED_BAR_FEATURES_RESEARCH_ONLY")
            self.assertEqual(r["feature_issuers"],1)
            f=r["features"][0]
            self.assertEqual(f["issuer"],"sh.600000")
            self.assertEqual(f["last_close_cny"],"10.40")
            self.assertTrue(f["above_ma20"])
            self.assertIsNone(f["sector"])
            self.assertFalse(f["buy_signal"])
            self.assertEqual(r["trade_gate"],"BLOCKED")
            self.assertEqual(r["orders"],[])
    def test_future_vendor_row_is_not_consumed(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d,future=True)
            r=observe(d,"2026-11-02")
            self.assertEqual(r["feature_issuers"],1)
            self.assertEqual(r["features"][0]["last_close_cny"],"10.40")
    def test_official_source_integrity_required(self):
        with tempfile.TemporaryDirectory() as d:
            folder=fixture(d)
            (folder/"sh_600000.csv").write_bytes(b"tampered")
            r=observe(d,"2026-11-02")
            self.assertEqual(r["status"],"REJECTED")
            self.assertEqual(r["reason"],"ARCHIVE_READ_OR_INTEGRITY_FAILURE")
    def test_missing_exact_asof_never_assumes_stale_last_close(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d)
            r=observe(d,"2026-11-03")
            self.assertEqual(r["feature_issuers"],0)
            self.assertEqual(r["evidence_gaps"][0]["reason"],"MISSING_EXACT_ASOF_CLOSE")
    def test_unverified_vendor_suspension_blocks_features(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d,last_status="0")
            r=observe(d,"2026-11-02")
            self.assertEqual(r["feature_issuers"],0)
            self.assertEqual(r["evidence_gaps"][0]["reason"],"VENDOR_NOT_TRADABLE_ASOF")
    def test_scope_does_not_silently_truncate(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d)
            # Additional verified issuer in another shard.
            second=Path(d)/"epoch"/"shard_0001"
            second.mkdir(parents=True)
            folder=Path(d)/"epoch"/"shard_0000"
            raw=(folder/"sh_600000.csv").read_bytes().replace(b"sh.600000",b"sz.002249")
            (second/"sz_002249.csv").write_bytes(raw)
            (second/"quality.json").write_text(json.dumps({
              "status":"OBSERVED_SUBSET_UNVERIFIED","trade_gate":"BLOCKED","orders":[],
              "historical_point_in_time_universe_verified":False,"issuer_count":1,
              "results":[{"code":"sz.002249","status":"OBSERVED_UNVERIFIED",
                 "sha256":hashlib.sha256(raw).hexdigest(),"rows":21,
                 "tradable_rows":21,"suspended_status_rows":0}]}))
            r=observe(d,"2026-11-02",max_issuers=1)
            self.assertEqual(r["reason"],"SCOPE_LIMIT_REACHED_REFUSE_PARTIAL")
    def test_invalid_root_or_asof_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(observe(d,"2026-11-02")["reason"],"NO_ORIGINAL_P2_RECEIPTS")
            self.assertEqual(observe(d,"invalid")["status"],"REJECTED")
if __name__=="__main__":unittest.main()
