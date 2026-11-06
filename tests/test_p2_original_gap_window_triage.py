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

    def test_unordered_duplicate_or_unknown_vendor_rows_fail_closed(self):
        asof="2026-10-22"
        valid=[row("2026-10-20"),row("2026-10-21","0"),row(asof)]
        with self.assertRaisesRegex(ValueError,"unordered"):
            classify([valid[1],valid[0],valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"duplicate"):
            classify([valid[0],valid[1],valid[1],valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"trade status"):
            classify([valid[0],row("2026-10-21","UNKNOWN"),valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"row date"):
            classify([valid[0],row("2026-02-30"),valid[2]],asof=asof)
        with self.assertRaisesRegex(ValueError,"as-of"):
            classify(valid,asof="2026-02-30")
        # A later original vendor row must not be silently used to fill an
        # earlier as-of research window.
        result=classify(valid+[row("2026-10-23")],asof=asof)
        self.assertEqual(result["available_vendor_rows_through_asof"],3)
        self.assertFalse(result["official_halt_explanation_authenticated"])

    def test_complete_window_not_a_gap_and_no_source_fabrication(self):
        rows=[row(f"2026-10-{i:02d}") for i in range(2,23)]
        with self.assertRaises(ValueError):classify(rows,asof="2026-10-22")
        with self.assertRaises(ValueError):classify(rows[:-1],asof="2026-10-22")
        with self.assertRaises(ValueError):diagnose({},'.')

if __name__=="__main__":unittest.main()
