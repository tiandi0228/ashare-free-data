import unittest
from collector.p3_real_official_discovery_queue import targets
class Tests(unittest.TestCase):
    def test_missing_only_and_no_fabricated_urls(self):
        w={"phase":"P3_P1_OBSERVED_WORKLIST","source_sha256":"a"*64,
           "trade_gate":"BLOCKED","official_evidence_cells_required":3,
           "official_evidence_tasks":[{"code":"sz.000001","kind":"st","decision_date":d} for d in ["2026-10-19","2026-10-20"]]+[{"code":"sz.000001","kind":"halt","decision_date":"2026-10-20"}]}
        s={"phase":"P3_FREE_OFFICIAL_MULTI_ISSUER_PROBE","trade_gate":"BLOCKED",
           "sources":[{"source_id":"a","issuer":"sz.000001","event_kind":"ST_CHANGE","original_bytes_verified":True,"event_contents_certified":True}]}
        q=targets(w,s)
        self.assertEqual(q["unmatched_cells"],1)
        self.assertEqual(q["targets"][0]["event_kind"],"halt")
        self.assertIsNone(q["targets"][0]["original_official_url"])
        self.assertFalse(q["official_PIT_verified"])
if __name__=="__main__":unittest.main()
