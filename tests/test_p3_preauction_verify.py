from datetime import datetime, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from collector.p3_preauction_receipt import SHANGHAI
from collector.p3_preauction_trial import run_trial
from collector.p3_preauction_verify import verify
from collector.p3_sina_preauction_probe import build_result


class VerifyTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.out = Path(temp.name) / "trial"
        self.t = datetime(2026, 11, 17, 9, 13, tzinfo=SHANGHAI)
        run_trial(self.t.date(), self.out, clock=lambda: self.t, wait=self.wait, fetch=self.fetch)

    def wait(self, seconds):
        self.t += timedelta(seconds=seconds)

    def fetch(self, issuer):
        fields = ["fixture"] + ["0"] * 29 + [str(self.t.date()), self.t.strftime("%H:%M:%S"), "03"]
        raw = ('var hq_str_' + issuer.replace(".", "") + '="' + ",".join(fields) + '";').encode()
        return build_result(raw, issuer, self.t.isoformat())

    def edit(self, file, **changes):
        path = self.out / file
        data = json.loads(path.read_text())
        data.update(changes)
        path.write_text(json.dumps(data))

    def test_valid_trial(self):
        result = verify(self.out)
        self.assertEqual(result["verified_receipts"], 6)
        self.assertEqual(result["same_day_preauction_observations"], 4)
        self.assertFalse(result["preauction_visibility_certified"])

    def test_changed_raw_bytes(self):
        self.edit("pre_early_sh.600825.json", raw_base64="dGFtcGVy")
        with self.assertRaises(ValueError):
            verify(self.out)

    def test_changed_hash_and_claim(self):
        self.edit("pre_early_sh.600825.json", raw_sha256="0" * 64, normalized_status_claim="HALTED")
        with self.assertRaisesRegex(ValueError, "response mismatch"):
            verify(self.out)

    def test_wrong_total(self):
        self.edit("summary.json", same_day_preauction_observations=6)
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            verify(self.out)
