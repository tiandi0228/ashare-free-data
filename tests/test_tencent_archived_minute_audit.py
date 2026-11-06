"""No live market request. Replay only self-generated fixture bytes."""
import json
import tempfile
import unittest
from pathlib import Path
from collector.tencent_eight_sample_pilot import collect
from collector.tencent_archived_minute_audit import replay

def quote_data(symbols):
    chunks=[]
    for s in symbols:
        fields=[""]*39
        fields[1]="测试"
        fields[2]=s[2:]
        fields[3]="10"
        fields[4]="9"
        fields[30]="20261106093500"
        chunks.append('v_'+s+'="'+'~'.join(fields)+'";')
    return ("\n".join(chunks)).encode("gb18030")

def minute_data(sym,period):
    width=int(period[1:])
    # Two synthetic bars exactly period minutes apart, valid session.
    from datetime import datetime,timedelta
    base=datetime(2026,11,6,9,35)
    rows=[]
    for t in (base,base+timedelta(minutes=width)):
        rows.append([t.strftime("%Y%m%d%H%M"),"10","10.1","10.2","9.9","100"])
    return json.dumps({"code":0,"data":{sym:{period:rows}}}).encode()

class TestArchiveReplay(unittest.TestCase):
    def fixture(self,root):
        dest=Path(root)/"archive"
        collect(dest,quote_transport=quote_data,minute_transport=minute_data)
        return dest

    def test_replay_ten_periods_and_one_quote(self):
        with tempfile.TemporaryDirectory() as td:
            out=replay(self.fixture(td))
            self.assertEqual(out["source_requests_replayed"],11)
            self.assertEqual(out["period_gap_count"],0)
            self.assertTrue(out["source_sha256_reverified"])
            self.assertFalse(out["independent_vendor_confirmed"])
            self.assertFalse(out["historical_PIT_verified"])
            self.assertEqual(out["trade_gate"],"BLOCKED")

    def test_original_receipt_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder=self.fixture(td)
            f=folder/"01_sh600519_m1"/"response.bin"
            f.write_bytes(f.read_bytes()+b" ")
            with self.assertRaises(ValueError):
                replay(folder)

    def test_stored_normalization_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder=self.fixture(td)
            f=folder/"02_sh600519_m5"/"bars.json"
            rows=json.loads(f.read_text())
            rows[0]["close"]=50
            f.write_text(json.dumps(rows))
            with self.assertRaises(ValueError):
                replay(folder)

    def test_source_summary_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder=self.fixture(td)
            f=folder/"summary.json"
            q=json.loads(f.read_text())
            q["results"][1]["symbol"]="sz002249"
            f.write_text(json.dumps(q))
            with self.assertRaises(ValueError):
                replay(folder)

if __name__=="__main__":
    unittest.main()
