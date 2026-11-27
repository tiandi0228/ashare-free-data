import csv,io,unittest
from collector.p2_sector_return_input import return_window,ASOF
from collector.p2_independent_bars import FIELDS
from collector.p4_curated_session_exit import sessions_between
class ReturnTests(unittest.TestCase):
    def raw(self,halt=False,missing=False):
        dates=sessions_between("2026-10-21",ASOF)
        stream=io.StringIO();w=csv.writer(stream);w.writerow(FIELDS)
        for i,d in enumerate(dates):
            if missing and i==len(dates)-5:continue
            p=str(10+i)
            w.writerow([d,"sh.600001",p,p,p,p,"100","1000","3","0" if halt and i==len(dates)-5 else "1"])
        return stream.getvalue().encode()
    def test_valid(self):
        r=return_window(self.raw(),"sh.600001")
        self.assertTrue(r["window_verified"]);self.assertGreater(float(r["return20_pct"]),0)
    def test_halt(self):
        self.assertFalse(return_window(self.raw(halt=True),"sh.600001")["window_verified"])
    def test_missing(self):
        self.assertFalse(return_window(self.raw(missing=True),"sh.600001")["window_verified"])
