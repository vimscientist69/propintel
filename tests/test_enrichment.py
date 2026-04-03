import unittest
from unittest.mock import patch

from backend.services.enrichment import enrich_lead
from backend.services.verifier import verify_lead


class TestWebsiteEnrichment(unittest.TestCase):
    def setUp(self) -> None:
        self.website_cfg = {
            "enabled": True,
            "discover_with_serper": True,
            "max_retries": 2,
            "request_timeout_seconds": 5,
            "serper_timeout_seconds": 5,
            "user_agent": "PropIntelTest/0.1",
            "chatbot_keywords": ["chatbot", "intercom", "live chat"],
        }

    def test_skip_when_no_website_and_not_discovered(self) -> None:
        lead = {
            "company_name": "Acme Realty",
            "website": "",
            "email": None,
            "phone": None,
        }
        with patch("backend.services.enrichment.discover_company_website", return_value=None):
            enriched = verify_lead(enrich_lead(lead, self.website_cfg))
        self.assertEqual(enriched.get("company_name"), "Acme Realty")
        self.assertIsNone(enriched.get("email"))
        self.assertEqual(enriched.get("contact_quality"), "low")

    def test_discover_then_extract_contacts(self) -> None:
        lead = {
            "company_name": "Acme Realty",
            "location": "Cape Town",
            "website": "",
            "email": None,
            "phone": None,
        }
        with patch(
            "backend.services.enrichment.discover_company_website",
            return_value="https://acme.co.za",
        ), patch(
            "backend.services.enrichment.fetch_website_html",
            return_value={"ok": True, "html": "<html>chatbot</html>", "error": None},
        ), patch(
            "backend.services.enrichment.extract_contacts_from_html",
            return_value={
                "emails": ["hello@acme.co.za"],
                "phones": ["+27 82 555 0199"],
            },
        ):
            enriched = verify_lead(enrich_lead(lead, self.website_cfg))

        self.assertEqual(enriched.get("website"), "https://acme.co.za")
        self.assertIsNotNone(enriched.get("email"))
        self.assertIsNotNone(enriched.get("phone"))
        self.assertTrue(enriched.get("has_chatbot"))
        self.assertEqual(enriched.get("contact_quality"), "verified")

    def test_fetch_error_is_non_fatal(self) -> None:
        lead = {
            "company_name": "Acme Realty",
            "website": "https://acme.co.za",
            "email": None,
            "phone": None,
        }
        with patch(
            "backend.services.enrichment.fetch_website_html",
            return_value={"ok": False, "html": "", "error": "timeout"},
        ), patch(
            "backend.services.enrichment.discover_company_website",
            return_value="https://new-acme.co.za",
        ):
            enriched = verify_lead(enrich_lead(lead, self.website_cfg))
        self.assertEqual(enriched.get("website"), "https://new-acme.co.za")
        self.assertEqual(enriched.get("enrichment_error"), "timeout")
        self.assertEqual(enriched.get("contact_quality"), "low")

    def test_fetch_error_and_discovery_disabled_sets_website_null(self) -> None:
        lead = {
            "company_name": "Acme Realty",
            "website": "https://acme.co.za",
            "email": None,
            "phone": None,
        }
        cfg = dict(self.website_cfg)
        cfg["discover_with_serper"] = False
        with patch(
            "backend.services.enrichment.fetch_website_html",
            return_value={"ok": False, "html": "", "error": "timeout"},
        ):
            enriched = verify_lead(enrich_lead(lead, cfg))
        self.assertIsNone(enriched.get("website"))
        self.assertEqual(enriched.get("contact_quality"), "low")


if __name__ == "__main__":
    unittest.main()

