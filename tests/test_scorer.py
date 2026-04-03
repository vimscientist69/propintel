import unittest

from backend.services.scorer import confidence_from_score, score_lead


FIXTURE_CFG: dict = {
    "base_score": 45,
    "weights": {
        "contact_quality_verified": 25,
        "contact_quality_likely": 10,
        "contact_quality_low": -15,
        "both_channels_bonus": 5,
        "chatbot_penalty": -10,
        "last_updated_bonus": 5,
        "last_updated_unknown_penalty": 0,
        "has_website": 10,
        "google_maps_source_bonus": 5,
        "has_location_bonus": 3,
        "has_agent_name_bonus": 2,
    },
}


def _base_verified_lead() -> dict:
    return {
        "company_name": "Acme",
        "contact_quality": "verified",
        "verification": {
            "email": {"valid": True, "normalized": "a@b.co"},
            "phone": {"valid": True, "normalized": "+27123456789"},
        },
        "website": "https://acme.co.za",
        "has_chatbot": False,
        "last_updated_signal": "detected",
        "source": "input",
    }


class TestScorer(unittest.TestCase):
    def test_verified_no_chatbot_fresh_website_exact_score(self) -> None:
        lead = _base_verified_lead()
        score, reason = score_lead(lead, FIXTURE_CFG)
        # 45 + 25 + 10 + 5 (freshness) = 85
        self.assertEqual(score, 85)
        self.assertIn("verified", reason.lower())
        self.assertIn("Freshness", reason)

    def test_chatbot_penalty_delta(self) -> None:
        with_bot = {**_base_verified_lead(), "has_chatbot": True}
        without = _base_verified_lead()
        s1, _ = score_lead(with_bot, FIXTURE_CFG)
        s2, _ = score_lead(without, FIXTURE_CFG)
        self.assertEqual(s2 - s1, 10)
        self.assertIn("Chatbot", score_lead(with_bot, FIXTURE_CFG)[1])

    def test_contact_quality_ordering(self) -> None:
        base = {
            "website": "https://x.co",
            "has_chatbot": False,
            "last_updated_signal": "unknown",
            "source": "input",
            "verification": {"email": {"valid": True}, "phone": {"valid": True}},
        }
        sv, _ = score_lead({**base, "contact_quality": "verified"}, FIXTURE_CFG)
        sl, _ = score_lead({**base, "contact_quality": "likely"}, FIXTURE_CFG)
        slo, _ = score_lead({**base, "contact_quality": "low"}, FIXTURE_CFG)
        self.assertGreater(sv, sl)
        self.assertGreater(sl, slo)

    def test_likely_both_channels_bonus(self) -> None:
        lead = {
            "contact_quality": "likely",
            "verification": {
                "email": {"valid": True},
                "phone": {"valid": True},
            },
            "website": "https://x.co",
            "has_chatbot": False,
            "last_updated_signal": "unknown",
            "source": "input",
        }
        score, _ = score_lead(lead, FIXTURE_CFG)
        # 45 + 10 + 5 + 10 + 0 = 70
        self.assertEqual(score, 70)

    def test_google_maps_and_location_bonuses(self) -> None:
        lead = {
            "contact_quality": "likely",
            "verification": {"email": {"valid": True}, "phone": {"valid": False}},
            "website": "https://x.co",
            "has_chatbot": False,
            "last_updated_signal": "unknown",
            "source": "input,google_maps",
            "location": "Cape Town",
            "agent_name": "Jane",
        }
        score, reason = score_lead(lead, FIXTURE_CFG)
        self.assertIn("Google Maps", reason)
        self.assertIn("Location", reason)
        self.assertIn("Agent", reason)
        self.assertGreater(score, 60)

    def test_confidence_from_score(self) -> None:
        self.assertEqual(confidence_from_score(82), 82)
        self.assertEqual(confidence_from_score(150), 100)


if __name__ == "__main__":
    unittest.main()
