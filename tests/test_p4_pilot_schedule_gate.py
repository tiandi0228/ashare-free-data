import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from collector.p4_pilot_schedule_gate import check, FIELDS

NOW=datetime(2026,12,1,11,40,tzinfo=timezone.utc)

def client(row, *, fields=FIELDS, next_values=(True,False)):
    c=Mock()
    c.login.return_value.error_code="0"
    r=c.query_trade_dates.return_value
    r.error_code="0"
    r.fields=fields
    r.next.side_effect=next_values
    r.get_row_data.return_value=row
    return c

class ScheduleGateTests(unittest.TestCase):
    def test_disabled_and_outside_window_never_access_vendor(self):
        p=Mock()
        for now,enabled in [(NOW,False),(NOW,"true"),(NOW.replace(month=11),True),(NOW.replace(day=5),True),(NOW.replace(hour=10),True)]:
            self.assertFalse(check(now,p,enabled=enabled)["allowed"])
        p.assert_not_called()

    def test_vendor_open_and_closed(self):
        for flag in ("0","1"):
            c=client(["2026-12-01",flag])
            r=check(NOW,lambda:c,enabled=True)
            self.assertEqual(r["allowed"],flag=="1")
            self.assertFalse(r["official_session_verified"])
            self.assertEqual(r["trade_gate"],"BLOCKED")
            self.assertEqual(r["orders"],[])
            c.logout.assert_called_once()

    def test_missing_wrong_day_duplicate_and_invalid_flag_fail_closed(self):
        for c in [client([],next_values=(False,)),client(["2026-12-02","1"]),client(["2026-12-01","1"],next_values=(True,True)),client(["2026-12-01","yes"]),client(["2026-12-01","1"],fields=["wrong"])]:
            with self.assertRaises(ValueError):
                check(NOW,lambda:c,enabled=True)
            c.logout.assert_called_once()
