"""Dated historical issuer pool is *vendor research*, never official PIT."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from collector.baostock_dated_universe import FIELDS, csv_bytes
from collector.audit_dated_rosters import (
    FROZEN, audit_archive, parse_source, validate_day
)


def original_fixture():
    rows=[[f"sh.{600000+i:06d}","1","测试公司"] for i in range(1000)]
    rows.append(["sh.603019","0","*ST测试"])
    original=csv_bytes(rows)
    return rows,original


class DatedOriginalReplayTests(unittest.TestCase):
    def test_real_two_historical_roster_source_digest_anchors(self):
        self.assertEqual(FROZEN["2025-05-26"]["main_rows"],3181)
        self.assertEqual(FROZEN["2026-10-20"]["main_rows"],3195)
        self.assertEqual(FROZEN["2025-05-26"]["halt_603019"],"0")
        self.assertEqual(FROZEN["2026-10-20"]["halt_603019"],"1")
        self.assertTrue(all(
            len(value[key])==64
            for value in FROZEN.values()
            for key in ("all_sha","main_sha")
        ))

    def test_fixture_first_party_derived_csv_rows_are_exactly_replayable(self):
        rows,raw=original_fixture()
        original,main=parse_source(raw)
        self.assertEqual(original,rows)
        self.assertEqual(main,rows)
        self.assertEqual(len(main),1001)

    def test_custom_frozen_case_checks_status_and_name_without_pit_approval(self):
        rows,raw=original_fixture()
        digest=hashlib.sha256(raw).hexdigest()
        sample={"2025-05-26":{
            "all_rows":1001,"main_rows":1001,"active":1000,
            "halted":1,"st_name_count":1,"all_sha":digest,"main_sha":digest,
            "halt_603019":"0",
        }}
        receipt={
            "date":"2025-05-26","status":"OBSERVED_UNVERIFIED",
            "mainboard_prefix_only":True,
            "source_all_security_rows":1001,
            "mainboard_prefix_rows":1001,
            "original_csv_sha256":digest,
            "mainboard_csv_sha256":digest,
            "mainboard_status_1":1000,
            "mainboard_status_0":1,
            "st_name_flags_observed_not_authoritative":1,
            "known_halt_case_status":"0",
        }
        r=validate_day("2025-05-26",raw,raw,receipt,sample)
        self.assertEqual(r["mainboard_prefix_rows"],1001)
        self.assertEqual(r["mainboard_st_name_flags"],1)
        self.assertFalse(r["exchange_official_asof_verified"])
        self.assertTrue(r["original_csv_reverified_in_this_audit"])

    def test_one_byte_tamper_rejected_by_SHA(self):
        rows,raw=original_fixture()
        digest=hashlib.sha256(raw).hexdigest()
        frozen={"2025-05-26":{
            "all_rows":1001,"main_rows":1001,"active":1000,"halted":1,
            "st_name_count":1,"all_sha":digest,"main_sha":digest,
            "halt_603019":"0",
        }}
        receipt={"date":"2025-05-26","status":"OBSERVED_UNVERIFIED",
                 "mainboard_prefix_only":True,
                 "original_csv_sha256":digest,"mainboard_csv_sha256":digest}
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            validate_day("2025-05-26",raw+b" ",raw,receipt,frozen)

    def test_issuer_duplicate_or_nonmainboard_not_eligible(self):
        rows,_=original_fixture()
        with self.assertRaisesRegex(ValueError,"duplicate"):
            parse_source(csv_bytes(rows+[rows[0]]))
        subset=[["sz.300750","1","创业板"] for _ in range(1001)]
        with self.assertRaises(ValueError):
            parse_source(csv_bytes(subset))

    def test_missing_archive_must_not_recover_from_sha_alone(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"unavailable"):
                audit_archive(Path(root,"expired_original.zip"))

    def test_forged_archive_missing_one_date_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root,"rosters.zip")
            with ZipFile(p,"w") as z:
                z.writestr("quality.json","{}")
                z.writestr("all_securities_2025-05-26.csv","empty")
            with self.assertRaisesRegex(ValueError,"Unexpected/missing"):
                audit_archive(p)


if __name__=="__main__":
    unittest.main()
