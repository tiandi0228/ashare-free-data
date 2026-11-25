import unittest

from collector.p1_gap_probe_fingerprint import compare, fingerprint


def receipt(digest="a", issuer="sh.600001"):
    return dict(manifest_sha256="f" * 64, trade_gate="BLOCKED", issuer_count=1,
                results=[dict(code=issuer, sha256=digest * 64, status="OBSERVED_UNVERIFIED")])


class ProbeFingerprintTests(unittest.TestCase):
    def test_same_bytes_do_not_certify_archive(self):
        r = compare(fingerprint(receipt()), receipt())
        self.assertEqual((r["status"], r["matching_count"]), ("CSV_DIGESTS_MATCH", 1))
        self.assertFalse(r["archive_acceptance_verified"])

    def test_changed_bytes_are_flagged_not_silently_accepted(self):
        r = compare(fingerprint(receipt()), receipt("b"))
        self.assertEqual(r["changed_issuers"], ["sh.600001"])
        self.assertEqual(r["status"], "SOURCE_BYTES_DIFFER_REVIEW")

    def test_different_membership_rejected(self):
        with self.assertRaisesRegex(ValueError, "manifest or issuer"):
            compare(fingerprint(receipt()), receipt(issuer="sh.600002"))

    def test_invalid_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid verified issuer"):
            fingerprint(receipt("z"))
