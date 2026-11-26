import unittest
from copy import deepcopy
from collector.p3_halt_gap_priority import prioritize

def row(code="sh.600150",day="2026-08-14",entries=None):
    return dict(code=code,target_date=day,original_csv_sha256="a"*64,
                vendor_status="0",official_effective_date_authenticated=False,
                official_publication_time_authenticated=False,official_source_url=None,
                official_source_sha256=None,risk_state="UNVERIFIED",
                affected_entry_dates=entries or ["2026-08-11"])
def source(rows):
    return dict(trade_gate="BLOCKED",orders=[],executable_candidates=[],
                officially_certified_halt_dates=0,historical_PIT_trade_eligible=False,
                pending_official_evidence=rows,distinct_issuer_halt_dates=len(rows),
                vendor_suspended_exit_observations=sum(len(r["affected_entry_dates"]) for r in rows))

class PriorityTests(unittest.TestCase):
    def test_rank_and_reconcile(self):
        r=prioritize(source([row(),row("sz.002860",entries=["2026-08-10","2026-08-11"])]))
        self.assertEqual(r["tasks"][0]["code"],"sz.002860")
        self.assertEqual((r["issuer_tasks"],r["target_days"],r["affected_entries"]),(2,2,3))
        self.assertEqual(r["trade_gate"],"BLOCKED")
    def test_duplicate_and_bad_dates(self):
        for rows in ([row(),row()], [row(entries=["2026-08-14"])], [row(entries=["2026-08-11","2026-08-11"])]):
            with self.assertRaises(ValueError):
                prioritize(source(rows))
    def test_false_certification_or_conflicting_sha(self):
        a=row();a["official_publication_time_authenticated"]=True
        with self.assertRaises(ValueError):
            prioritize(source([a]))
        b=row(day="2026-08-17");b["original_csv_sha256"]="b"*64
        with self.assertRaises(ValueError):
            prioritize(source([row(),b]))
