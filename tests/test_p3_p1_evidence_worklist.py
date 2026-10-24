import csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from collector.p3_p1_evidence_worklist import worklist

class WorklistTests(unittest.TestCase):
    def test_worklist_and_wrong_epoch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source="a"*64
            part=root/source[:16]/"shard_0000";part.mkdir(parents=True)
            with (part/"sh_600000.csv").open("w") as f:
                f.write("date,tradestatus,close\n2026-10-19,0,10\n2026-10-20,1,11\n")
            plan={"source_sha256":source}
            ledger={"source_sha256":source,"trade_gate":"BLOCKED","completed":[{"index":0}]}
            with patch("collector.p3_p1_evidence_worklist.assess",return_value={"details":[{"code":"sh.600000"}]}):
                q=worklist(root,plan,ledger)
                self.assertEqual(q["official_evidence_cells_pending"],8)
                self.assertEqual(q["vendor_status_observed_not_official"]["sh.600000"]["2026-10-19"],"0")
                self.assertEqual(len(q["official_evidence_tasks"]),8)
                self.assertTrue(all(x["status"]=="OFFICIAL_EVIDENCE_REQUIRED" for x in q["official_evidence_tasks"]))
                self.assertEqual(q["official_evidence_cells_verified"],0)
                self.assertEqual(q["trade_gate"],"BLOCKED")
                with self.assertRaises(ValueError):worklist(root,{"source_sha256":"b"*64},ledger)
if __name__=="__main__":unittest.main()
