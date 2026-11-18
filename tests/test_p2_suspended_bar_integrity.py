"""Regression checks for non-executable BaoStock suspended daily rows."""
import unittest

from collector.p2_independent_bars import audit_csv

HEADER = "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus"
CODE = "sh.600130"


def csv_row(*, status="0", volume="", amount="", ohlc=("2.5500",) * 4):
    return (
        f"{HEADER}\n"
        f"2025-04-29,{CODE},{','.join(ohlc)},{volume},{amount},3,{status}\n"
    ).encode("utf-8")


class SuspendedBarAuditTests(unittest.TestCase):
    def test_realistic_empty_turnover_suspended_row_is_nontradable(self):
        result = audit_csv(csv_row(), CODE)
        self.assertEqual(result["vendor_suspended_rows"], 1)
        self.assertEqual(result["active_rows"], 0)

    def test_explicit_zero_turnover_is_also_accepted_as_suspended(self):
        result = audit_csv(csv_row(volume="0", amount="0.0000"), CODE)
        self.assertEqual(result["vendor_suspended_rows"], 1)

    def test_missing_all_suspended_ohlc_is_not_a_fill(self):
        result = audit_csv(csv_row(ohlc=("",) * 4), CODE)
        self.assertEqual(result["active_rows"], 0)
        self.assertEqual(result["vendor_suspended_rows"], 1)

    def test_suspended_positive_turnover_rejected(self):
        for field in ("volume", "amount"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit_csv(csv_row(**{field: "100"}), CODE)

    def test_suspended_negative_or_nonfinite_turnover_rejected(self):
        for value in ("-1", "nan", "inf", "bad"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit_csv(csv_row(volume=value), CODE)

    def test_suspended_partial_or_invalid_ohlc_rejected(self):
        for ohlc in (
            ("2.55", "", "2.55", "2.55"),
            ("nan", "2.55", "2.55", "2.55"),
            ("2.55", "2.50", "2.55", "2.55"),
        ):
            with self.subTest(ohlc=ohlc), self.assertRaises(ValueError):
                audit_csv(csv_row(ohlc=ohlc), CODE)

    def test_active_missing_turnover_is_rejected(self):
        for volume, amount in (("", "100"), ("100", "")):
            with self.subTest(volume=volume, amount=amount), self.assertRaises(ValueError):
                audit_csv(csv_row(status="1", volume=volume, amount=amount), CODE)

    def test_active_numeric_turnover_remains_accepted(self):
        result = audit_csv(csv_row(status="1", volume="100", amount="255"), CODE)
        self.assertEqual((result["active_rows"], result["vendor_suspended_rows"]), (1, 0))

    def test_unknown_status_is_rejected(self):
        for status in ("", "2", "UNKNOWN"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                audit_csv(csv_row(status=status), CODE)


if __name__ == "__main__":
    unittest.main()
