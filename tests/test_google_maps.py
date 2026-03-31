import os
import unittest
from unittest.mock import patch

from backend.services.google_maps import enrich_lead_from_google_maps, match_best_candidate


class TestGoogleMapsEnrichment(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {
            "enabled": True,
            "timeout_seconds": 5,
            "max_retries": 1,
            "min_name_match_score": 0.5,
            "region": "za",
            "language": "en",
        }

    def test_name_only_match_when_location_missing(self) -> None:
        lead = {
            "company_name": "Southern Cape Properties",
            "location": "",
            "website": None,
            "phone": None,
            "source": "input",
        }

        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "x"}, clear=False), patch(
            "backend.services.google_maps.normalize_location",
            return_value=None,
        ), patch(
            "backend.services.google_maps.search_places",
            return_value=[
                {
                    "name": "Southern Cape Properties",
                    "formatted_address": "77 Knysna Road, George, South Africa",
                    "place_id": "abc123",
                }
            ],
        ), patch(
            "backend.services.google_maps.get_place_details",
            return_value={
                "website": "https://www.scprop.co.za/",
                "formatted_phone_number": "044 001 0004",
                "formatted_address": "77 Knysna Road, George, South Africa",
            },
        ):
            enriched = enrich_lead_from_google_maps(lead, self.cfg)

        self.assertEqual(enriched.get("website"), "https://www.scprop.co.za/")
        self.assertEqual(enriched.get("phone"), "044 001 0004")
        self.assertIn("google_maps", str(enriched.get("source")))

    def test_invalid_location_replaced_with_formatted_address(self) -> None:
        lead = {
            "company_name": "Southern Cape Properties",
            "location": "bad-format-location",
            "source": "input",
        }
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "x"}, clear=False), patch(
            "backend.services.google_maps.normalize_location",
            return_value=None,
        ), patch(
            "backend.services.google_maps.search_places",
            return_value=[
                {
                    "name": "Southern Cape Properties",
                    "formatted_address": "77 Knysna Road, George, South Africa",
                    "place_id": "abc123",
                }
            ],
        ), patch(
            "backend.services.google_maps.get_place_details",
            return_value={
                "formatted_address": "77 Knysna Road, George, South Africa",
            },
        ):
            enriched = enrich_lead_from_google_maps(lead, self.cfg)

        self.assertEqual(enriched.get("location"), "77 Knysna Road, George, South Africa")

    def test_candidate_rejected_by_name_threshold(self) -> None:
        candidates = [
            {
                "name": "Random Company",
                "formatted_address": "Cape Town, South Africa",
                "place_id": "x",
            }
        ]
        lead = {"company_name": "Southern Cape Properties", "location": "George"}
        chosen = match_best_candidate(
            candidates,
            lead,
            min_name_match_score=0.95,
            normalized_location="George, South Africa",
        )
        self.assertIsNone(chosen)

    def test_missing_api_key_is_non_fatal(self) -> None:
        lead = {"company_name": "Southern Cape Properties", "source": "input"}

        with patch("backend.services.google_maps._load_env", return_value=None), \
            patch("backend.services.google_maps.os.getenv", return_value=None):
            enriched = enrich_lead_from_google_maps(lead, self.cfg)

        self.assertEqual(enriched.get("google_maps_error"), "missing_api_key")

if __name__ == "__main__":
    unittest.main()

