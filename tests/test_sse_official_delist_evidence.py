"""Offline tamper and temporal-semantics contracts for SSE official page pair."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from collector.sse_official_delist_evidence import (
    COMPANY, SOURCES, capture, inspect_document,
)


def fake_html(spec):
    body = " ".join(spec["needles"])
    return ("<!DOCTYPE html><html><meta charset='utf-8'><body><article>"
            + body + "</article></body></html>").encode("utf-8")


class OfficialSourceTests(unittest.TestCase):
    def test_two_pages_success_still_blocks_formal_pit(self):
        seen = []
        def get(url):
            seen.append(url)
            spec = next(x for x in SOURCES if x["url"] == url)
            return fake_html(spec), url
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(capture(root, get), 0)
            self.assertEqual(seen, [x["url"] for x in SOURCES])
            q = json.loads((Path(root) / "quality.json").read_text())
            self.assertEqual(q["attempted_gets"], 2)
            self.assertEqual(q["trade_gate"], "BLOCKED")
            self.assertEqual(q["orders"], [])
            self.assertFalse(q["issuer_tradability_certified"])
            self.assertFalse(q["historical_point_in_time_universe_verified"])
            a, b = q["page_events"]
            self.assertEqual(a["event"], "DELIST_DECISION_ONLY")
            self.assertIsNone(a["effective_delist_date"])
            self.assertEqual(b["event"], "DELIST_EFFECTIVE_DATE_ANNOUNCED")
            self.assertEqual(b["effective_delist_date"], "2026-06-26")
            self.assertEqual(a["conservative_next_calendar_day_for_review"], "2026-05-23")
            self.assertEqual(b["conservative_next_calendar_day_for_review"], "2026-06-23")
            self.assertEqual(a["page_content_sha256"], hashlib.sha256(fake_html(SOURCES[0])).hexdigest())

    def test_swapped_page_does_not_pass(self):
        with tempfile.TemporaryDirectory() as root:
            def getter(url):
                other = SOURCES[1] if url == SOURCES[0]["url"] else SOURCES[0]
                return fake_html(other), url
            self.assertEqual(capture(root, getter), 2)
            result = json.loads((Path(root) / "quality.json").read_text())
            self.assertEqual(result["status"], "BLOCKED_PARTIAL")
            self.assertEqual(result["executable_candidates"], [])

    def test_unexpected_origin_or_redirect_refused(self):
        with self.assertRaisesRegex(ValueError, "URL did not match"):
            inspect_document(SOURCES[0], fake_html(SOURCES[0]), "https://example.com/other")
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(capture(root, lambda u: (fake_html(SOURCES[0]), "https://other.test")), 2)

    def test_decision_page_cannot_substitute_for_effective_date(self):
        wrong = fake_html(SOURCES[1]).replace("2026年6月26日", "2026年5月22日".encode("utf-8"))
        with self.assertRaisesRegex(ValueError, "anchor missing"):
            inspect_document(SOURCES[1], wrong, SOURCES[1]["url"])

    def test_bounded_empty_or_http_error_no_trade(self):
        for client in (lambda url: (b"", url),
                       lambda url: (_ for _ in ()).throw(TimeoutError("offline"))):
            with self.subTest(client=client), tempfile.TemporaryDirectory() as root:
                self.assertEqual(capture(root, client), 2)
                q = json.loads((Path(root) / "quality.json").read_text())
                self.assertEqual(q["attempted_gets"], 2)
                self.assertEqual(q["trade_gate"], "BLOCKED")
                self.assertEqual(q["orders"], [])
                self.assertEqual(q["status"], "BLOCKED_PARTIAL")


if __name__ == "__main__":
    unittest.main()
