import copy
import unittest

from collector.p4_event_exposure_research import assess


def example():
    return {
        "asof": "2026-11-10",
        "event": {
            "name": "Publicized city international media-centre opening",
            "event_on": "2026-11-11",
            "schedule_published_on": "2026-11-08",
            "schedule_source": "https://example.org/official-event",
            "source_authenticated": False,
        },
        "issuers": [
            {"issuer": "sz.000069", "exposure": "venue_named",
             "company_source": "https://example.org/report",
             "company_excerpt_sha256": "a"*64,
             "company_disclosed_on": "2026-10-20",
             "official_pit_non_st_halt_verified": False},
            {"issuer": "sz.000058", "exposure": "location_only",
             "official_pit_non_st_halt_verified": False},
        ],
    }


class P4EventExposureResearchTests(unittest.TestCase):
    def test_known_advance_event_not_buy_signal(self):
        r = assess(example())
        self.assertTrue(r["schedule_is_not_a_surprise_catalyst"])
        self.assertFalse(r["full_market_screen_performed"])
        self.assertEqual(r["trade_gate"], "BLOCKED")
        self.assertEqual(r["orders"], [])
        self.assertEqual(r["executable_candidates"], [])
        self.assertFalse(r["one_word_limit_up_can_be_predicted"])
        self.assertEqual(r["symbols"][0]["exposure_category"], "BUSINESS_LINK_ASSERTED_UNVERIFIED")
        self.assertEqual(r["symbols"][1]["exposure_category"], "GEOGRAPHIC_THEME_ONLY")
        self.assertFalse(r["symbols"][0]["buy_allowed"])

    def test_fake_signed_contract_not_promoted_to_authorized_buy(self):
        p = example()
        p["issuers"][0]["exposure"] = "signed_contract"
        p["issuers"][0]["official_pit_non_st_halt_verified"] = True
        p["event"]["source_authenticated"] = True
        r = assess(p)
        self.assertFalse(r["independent_external_source_replay_completed"])
        self.assertIn("NO_RECONCILED_CURRENT_EXECUTABLE_QUOTES", r["symbols"][0]["blockers"])
        self.assertFalse(r["symbols"][0]["buy_allowed"])

    def test_missing_source_sha_or_future_company_date_fails_closed(self):
        for key, value in (
            ("company_source", "no provenance"),
            ("company_excerpt_sha256", "wrong"),
            ("company_disclosed_on", "2026-11-11"),
        ):
            p = example()
            p["issuers"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                assess(p)

    def test_exposure_cannot_be_inferred_from_location(self):
        p = example()
        p["issuers"][1]["company_source"] = "https://example.org/unrelated"
        with self.assertRaisesRegex(ValueError, "location-only"):
            assess(p)

    def test_chronology_and_pit_cannot_be_guessed(self):
        for field, value in (("schedule_published_on", "2026-11-11"),
                             ("event_on", "2026-11-06")):
            p = example()
            p["event"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                assess(p)
        p = example()
        p["issuers"][0].pop("official_pit_non_st_halt_verified")
        with self.assertRaisesRegex(ValueError, "explicit PIT"):
            assess(p)

    def test_reject_chinext_duplicate_and_oversize(self):
        p = example()
        p["issuers"][0]["issuer"] = "sz.300015"
        with self.assertRaisesRegex(ValueError, "out-of-mainboard"):
            assess(p)
        p = example()
        p["issuers"][1]["issuer"] = "sz.000069"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            assess(p)
        p = example()
        p["issuers"] = p["issuers"]*26
        with self.assertRaisesRegex(ValueError, "bounded"):
            assess(p)

    def test_event_day_is_not_proof_of_reaction(self):
        p = example()
        p["asof"] = "2026-11-11"
        r = assess(p)
        self.assertFalse(r["symbols"][0]["price_direction_verified"])
        self.assertEqual(r["trade_gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
