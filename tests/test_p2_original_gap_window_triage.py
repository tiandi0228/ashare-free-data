import unittest
from collector.p2_original_gap_window_triage import classify,diagnose

def row(date,status="1"):
    return {"date":date,"tradestatus":status}

class GapSourceTests(unittest.TestCase):
    def test_fewer_21_vendor_rows_is_not_an_official_listing_date(self):
        sample=[row("2026-10-20"),row("2026-10-21"),row("2026-10-22")]
        x=classify(sample,asof="2026-10-22")
        self.assertEqual(x["diagnosis"],"FEWER_THAN_21_VENDOR_ROWS_ASOF")
        self.assertFalse(x["official_halt_explanation_authenticated"])
        self.assertFalse(x["vendor_row_window_is_calendar_coverage"])

    def test_suspended_vendor_row_in_last_21_must_not_be_bridged(self):
        rows=[row(f"2026-10-{i:02d}",status="0" if i==10 else "1")
              for i in range(2,23)]
        x=classify(rows,asof="2026-10-22")
        self.assertEqual(x["diagnosis"],"VENDOR_SUSPENDED_ROW_WITHIN_LAST_21")
        self.assertEqual(x["trailing_vendor_suspended_rows"],1)

    def test_complete_window_not_a_gap_and_no_source_fabrication(self):
        rows=[row(f"2026-10-{i:02d}") for i in range(2,23)]
        with self.assertRaises(ValueError):classify(rows,asof="2026-10-22")
        with self.assertRaises(ValueError):classify(rows[:-1],asof="2026-10-22")
        with self.assertRaises(ValueError):diagnose({},'.')

if __name__=="__main__":unittest.main()
