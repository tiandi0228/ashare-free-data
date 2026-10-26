import unittest
from collector.p3_official_scope_overlap import overlap
class OverlapTests(unittest.TestCase):
    def setup_data(self):
        return ({"phase":"P3_P1_OBSERVED_WORKLIST","trade_gate":"BLOCKED",
                "official_evidence_cells_required":2,
                "official_evidence_tasks":[{"code":"sh.600000","decision_date":"2026-10-20","kind":k} for k in ("st","halt")]},
                {"phase":"P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE","trade_gate":"BLOCKED",
                 "sources":[{"source_id":"a","issuer":"sh.600000","event_kind":"ST_CHANGE","original_bytes_verified":True,"event_contents_certified":True}]})
    def test_overlap_is_only_hint(self):
        w,s=self.setup_data();r=overlap(w,s)
        self.assertEqual(r["issuer_kind_source_overlap_cells"],1)
        self.assertEqual(r["official_pit_certified_cells"],0)
        self.assertEqual(r["unmatched_cells"],1)
    def test_no_cross_issuer_promotion(self):
        w,s=self.setup_data();s["sources"][0]["issuer"]="sz.000001"
        self.assertEqual(overlap(w,s)["issuer_kind_source_overlap_cells"],0)
    def test_duplicate_source_rejected(self):
        w,s=self.setup_data();s["sources"].append(dict(s["sources"][0]))
        with self.assertRaises(ValueError):overlap(w,s)
if __name__=="__main__":unittest.main()
