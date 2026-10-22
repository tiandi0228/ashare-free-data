"""Historical as-of availability cannot be inferred from a later source download."""
import json,unittest
from pathlib import Path
from collector.p3_capture_temporal_boundary import observe
ROOT=Path(__file__).resolve().parents[1]/"reports"
class TemporalBoundaryTests(unittest.TestCase):
 def test_two_real_publisher_receipts(self):
    a=json.loads((ROOT/"p3_cninfo_two_pdf_independent_sha_recapture_20261022.json").read_text())
    b=json.loads((ROOT/"p3_sse_two_official_original_sha_observed_20261022.json").read_text())
    result=observe(a,b)
    self.assertEqual(result["document_count"],4)
    self.assertFalse(result["historical_availability_verified"])
    self.assertTrue(all(not d["earlier_asof_availability_proven"] for d in result["documents"]))
    self.assertEqual(result["trade_gate"],"BLOCKED")
if __name__=="__main__":unittest.main()
