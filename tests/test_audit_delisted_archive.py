"""Offline tests for original CSV replay and delisting status detection."""
import csv
import io
import unittest

from collector.audit_delisted_archive import verify_rows, REQUIRED_STATES, LAST_STATUS_1
from collector.baostock_batch import FIELDS


def rows_bytes(records):
    out=io.StringIO(newline="")
    writer=csv.writer(out,lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(records)
    return out.getvalue().encode("utf-8")


def bar(day,code="sh.600519",state="1",price="10.00"):
    return [day,code,price,price,price,price,"100","1000","3",state]


class OriginalReplayTests(unittest.TestCase):
    def test_valid_rows_have_tradable_day_distinct_from_csv_end(self):
        v=verify_rows("sh.600519",rows_bytes([
            bar("2026-05-20"),
            bar("2026-05-21",state="0"),
        ]))
        self.assertEqual(v["source_rows"],2)
        self.assertEqual(v["trade_status_1_rows"],1)
        self.assertEqual(v["trade_status_0_rows"],1)
        self.assertEqual(v["last_status_1_date"],"2026-05-20")
        self.assertEqual(v["last_original_csv_date"],"2026-05-21")

    def test_duplicate_or_backward_dates_rejected(self):
        for arr in ([bar("2026-05-20"),bar("2026-05-20")],
                    [bar("2026-05-21"),bar("2026-05-20")]):
            with self.subTest(arr=arr),self.assertRaisesRegex(ValueError,"ordering"):
                verify_rows("sh.600519",rows_bytes(arr))

    def test_wrong_issuer_or_status_rejected(self):
        with self.assertRaisesRegex(ValueError,"identity"):
            verify_rows("sh.600519",rows_bytes([bar("2026-05-20",code="sh.600421")]))
        with self.assertRaisesRegex(ValueError,"status"):
            verify_rows("sh.600519",rows_bytes([bar("2026-05-20",state="2")]))

    def test_non_positive_or_malformed_ohlc_rejected(self):
        with self.assertRaisesRegex(ValueError,"OHLC"):
            verify_rows("sh.600519",rows_bytes([bar("2026-05-20",price="0")]))
        bad=bar("2026-05-20")
        bad[3]="9.00"
        with self.assertRaisesRegex(ValueError,"OHLC"):
            verify_rows("sh.600519",rows_bytes([bad]))

    def test_bad_schema_and_truncated_row_rejected(self):
        with self.assertRaisesRegex(ValueError,"schema"):
            verify_rows("sh.600519",b"date,code\n2026-05-20,sh.600519\n")
        with self.assertRaisesRegex(ValueError,"Malformed"):
            verify_rows("sh.600519",rows_bytes([bar("2026-05-20")])[:-15])

    def test_frozen_delisted_case_requires_event_states(self):
        self.assertEqual(LAST_STATUS_1,"2026-06-22")
        self.assertEqual(REQUIRED_STATES["2026-06-23"],"0")
        with self.assertRaisesRegex(ValueError,"Known delisting-period"):
            verify_rows("sh.600421",rows_bytes([bar("2026-05-20",code="sh.600421")]))


if __name__=="__main__":
    unittest.main()
