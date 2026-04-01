import unittest

from backend.services.conflict_resolver import resolve_field_candidates


class TestConflictResolver(unittest.TestCase):
    def test_tie_prefers_google_maps_for_verified_website(self) -> None:
        candidates = [
            {
                "field": "website",
                "source": "website_enrichment",
                "value": "https://southerncapeproperties.co.za",
                "validated": True,
                "confidence": 0.86,
            },
            {
                "field": "website",
                "source": "google_maps",
                "value": "https://www.scprop.co.za/",
                "validated": True,
                "confidence": 0.86,
            },
        ]
        value, decision = resolve_field_candidates(
            "website", candidates, current_value="https://southerncapeproperties.co.za"
        )
        self.assertEqual(value, "https://www.scprop.co.za/")
        self.assertTrue(decision["tie_break_applied"])
        self.assertEqual(decision["tie_break_reason"], "prefer_google_maps_if_verified")

    def test_non_website_tie_keeps_current(self) -> None:
        candidates = [
            {"field": "phone", "source": "website_enrichment", "value": "044 001 0004", "validated": True, "confidence": 0.8},
            {"field": "phone", "source": "google_maps", "value": "0440010004", "validated": True, "confidence": 0.8},
        ]
        value, decision = resolve_field_candidates("phone", candidates, current_value="044 001 0004")
        self.assertEqual(value, "044 001 0004")
        self.assertEqual(decision["tie_break_reason"], "keep_current_on_tie")


if __name__ == "__main__":
    unittest.main()

