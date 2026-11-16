import unittest
from collector.p3_000582_halt_replay import HALT_CLAUSE, RESUME_CLAUSE, check_rows, check_text, replay


class HaltReplayTests(unittest.TestCase):
    def test_requires_issuer_notice_and_same_clause_dates(self):
        header = "证券代码：000582 北部湾港 公告编号："
        halt = header + "2026059 " + HALT_CLAUSE
        resume = header + "2026061 " + HALT_CLAUSE + "\n" + RESUME_CLAUSE
        check_text(halt, resume)
        for change in (resume.replace("000582", "000583"), resume.replace("2026061", "2026059"),
                       resume.replace("开市起复牌", "开市起停牌"), resume.replace(HALT_CLAUSE, "")):
            with self.assertRaises(ValueError):
                check_text(halt, change)

    def test_requires_both_halt_rows_and_resume(self):
        raw = (b"date,code,tradestatus\n2026-10-08,sz.000582,0\n"
               b"2026-10-09,sz.000582,0\n2026-10-12,sz.000582,1\n")
        self.assertEqual(len(check_rows(raw)), 3)
        for bad in (raw.replace(b"10-09,sz.000582,0", b"10-09,sz.000582,1"),
                    raw.replace(b"2026-10-09,sz.000582,0\n", b""),
                    raw.replace(b"10-09", b"10-08")):
            with self.assertRaises(ValueError):
                check_rows(bad)

    def test_rejects_changed_pdf_before_parsing(self):
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            replay(b"%PDF-tampered", b"", b"")
