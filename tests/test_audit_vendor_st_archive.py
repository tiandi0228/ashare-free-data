"""Fail-closed tests for authentic vendor isST originals replay."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from collector.audit_vendor_st_archive import EXPECTED, audit


class VendorSTReplayTests(unittest.TestCase):
    def test_st_origin_pinned_to_both_real_SHA(self):
        self.assertEqual(set(EXPECTED), {"sh.600421","sh.603019"})
        self.assertEqual(EXPECTED["sh.600421"]["rows"],268)
        self.assertEqual(EXPECTED["sh.600421"]["vendor_ST_1_rows"],250)
        self.assertEqual(EXPECTED["sh.600421"]["vendor_halted_rows"],27)
        self.assertEqual(EXPECTED["sh.603019"]["vendor_halted_rows"],10)
        self.assertTrue(all(len(row["original_csv_sha256"])==64
                            for row in EXPECTED.values()))

    def test_missing_all_originals_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root,"source.zip")
            with ZipFile(p,"w") as z:
                z.writestr("quality.json","{}")
            with self.assertRaisesRegex(ValueError,"Unexpected source files"):
                audit(p)

    def test_invented_originals_cannot_pass(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root,"source.zip")
            with ZipFile(p,"w") as z:
                z.writestr("quality.json",'{"status":"OK"}')
                z.writestr("sh_600421_vendor_ST.csv","a,b,c\n")
                z.writestr("sh_603019_vendor_ST.csv","a,b,c\n")
            with self.assertRaisesRegex(ValueError,"research-only"):
                audit(p)

    def test_traversal_member_or_wrong_name_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root,"source.zip")
            with ZipFile(p,"w") as z:
                z.writestr("../quality.json","{}")
                z.writestr("sh_600421_vendor_ST.csv","x")
                z.writestr("sh_603019_vendor_ST.csv","x")
            with self.assertRaisesRegex(ValueError,"Unexpected source files"):
                audit(p)

    def test_missing_zip_is_not_reconstructed_from_a_digest(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"absent"):
                audit(Path(root,"unavailable.zip"))

if __name__=="__main__":
    unittest.main()
