import json,tempfile,unittest
from pathlib import Path
from collector.p3_publication_bar_gap import join
class PublicationBarGapTests(unittest.TestCase):
    def test_link_is_not_certification(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bars.csv"
            p.write_text("date,code,close\n2026-10-19,sh.600421,1\n2026-10-20,sh.600421,1\n")
            e=[{"issuer":"sh.600421","kind":"DELIST_EFFECTIVE","original_sha256":"a"*64,
                "effective_date":"2026-10-20",
                "authenticated_first_published_at":"2026-10-19T08:00:00+08:00",
                "publisher_independently_authenticated":True,"original_bytes_verified":True,
                "publication_timestamp_independently_authenticated":True,"trade_gate":"BLOCKED","orders":[]}]
            r=join(p,e,"2026-10-20T09:30:00+08:00")
            self.assertEqual(r["linked_bar_rows"],2)
            self.assertEqual(r["event_links"][0]["rows_on_or_after_effective"],1)
            self.assertEqual(r["certified_issuer_day_state_rows"],0)
            self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_future_publication_not_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bars.csv";p.write_text("date,code\n2026-10-20,sh.600421\n")
            e=[{"issuer":"sh.600421","kind":"DELIST_EFFECTIVE","original_sha256":"a"*64,
                "effective_date":"2026-10-20","authenticated_first_published_at":"2026-10-20T18:00:00+08:00",
                "publisher_independently_authenticated":True,"original_bytes_verified":True,
                "publication_timestamp_independently_authenticated":True,"trade_gate":"BLOCKED","orders":[]}]
            self.assertFalse(join(p,e,"2026-10-20T09:30:00+08:00")["event_links"][0]["known_before_decision"])
    def test_partitions_by_shanghai_day_even_after_close(self):
        event = {"issuer": "sh.600421", "kind": "HALT_START",
                 "original_sha256": "a"*64, "effective_date": "2026-10-20",
                 "trade_gate": "BLOCKED", "orders": []}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bars.csv"
            p.write_text("date,code\n2026-10-19,sh.600421\n2026-10-20,sh.600421\n"
                         "2026-10-21,sh.600421\n2026-10-19,sh.600000\n")
            for instant in ("2026-10-19T16:30:00+00:00", "2026-10-20T09:30:00+00:00"):
                with self.subTest(instant=instant):
                    report = join(p, [event], instant)
                    row = report["event_links"][0]
                    self.assertEqual(report["decision_session_day_shanghai"], "2026-10-20")
                    self.assertEqual(report["linked_bar_rows"], 3)
                    self.assertEqual(row["prior_session_bar_rows"], 1)
                    self.assertEqual(row["decision_day_bar_rows_without_availability_clock"], 1)
                    self.assertEqual(row["future_session_bar_rows"], 1)
                    self.assertFalse(report["prior_session_rows_prove_asof_availability"])

    def test_rejects_duplicate_and_noncanonical_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bars.csv"
            for bad in ("20261019,sh.600421\n", "2026-10-19,sh.600421\n"*2):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    p.write_text("date,code\n"+bad)
                    join(p, [], "2026-10-20T09:30:00+08:00")
if __name__=="__main__":unittest.main()
