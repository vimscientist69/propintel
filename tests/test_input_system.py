import csv
import json
import tempfile
import unittest
from pathlib import Path

from backend.core.deduplicator import deduplicate
from backend.core.ingestion import run_ingestion_with_sources_config
from backend.core.normalizer import normalize_lead
from backend.core.parser import load_csv_mapped, map_row_to_canonical


class TestInputSystem(unittest.TestCase):
    def setUp(self) -> None:
        self.mapping_cfg = {
            "required_any": ["company_name"],
            "schema_aliases": {
                "company_name": ["company", "agency", "business"],
                "email": ["email", "contact_email"],
                "website": ["website", "url"],
                "phone": ["phone", "tel"],
            },
            "defaults": {"source": "input"},
        }

    def test_alias_mapping_happy_path(self) -> None:
        row = {
            "Company": "Acme Realty",
            "contact_email": "Info@Acme.co.za",
            "url": "https://www.acme.co.za/",
        }

        lead, reason = map_row_to_canonical(row, self.mapping_cfg)
        self.assertIsNotNone(lead)
        self.assertIsNone(reason)
        self.assertEqual(lead["company_name"], "Acme Realty")
        self.assertEqual(lead["email"], "Info@Acme.co.za")
        self.assertEqual(lead["website"], "https://www.acme.co.za/")
        self.assertEqual(lead["source"], "input")

    def test_required_identity_rejection(self) -> None:
        row = {"email": "info@example.com"}
        lead, reason = map_row_to_canonical(row, self.mapping_cfg)
        self.assertIsNone(lead)
        self.assertEqual(reason, "missing_required_identity")

    def test_load_csv_mapped_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "leads.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Company", "email", "website"])
                writer.writeheader()
                writer.writerow(
                    {
                        "Company": "Acme Realty",
                        "email": "info@acme.co.za",
                        "website": "acme.co.za",
                    }
                )
                writer.writerow(
                    {
                        "Company": "",
                        "email": "bad-email",
                        "website": "acme.co.za",
                    }
                )

            leads, rejected = load_csv_mapped(csv_path, self.mapping_cfg)
            self.assertEqual(len(leads), 1)
            self.assertEqual(len(rejected), 1)
            self.assertIn("reason", rejected[0])

    def test_normalize_and_deduplicate(self) -> None:
        leads = [
            {
                "company_name": "Acme Realty",
                "website": "https://www.acme.co.za/",
                "email": "INFO@ACME.CO.ZA",
                "phone": "+27 12 345 6789",
            },
            {
                "company_name": "Acme Realty",
                "website": "acme.co.za",
                "email": "info@acme.co.za",
                "phone": "+27 12 345 6789",
            },
        ]

        normalized = [normalize_lead(lead) for lead in leads]
        deduped = deduplicate(normalized)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["website"], "acme.co.za")

    def test_run_ingestion_emits_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "leads.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Company", "contact_email", "url"])
                writer.writeheader()
                writer.writerow(
                    {
                        "Company": "Acme Realty",
                        "contact_email": "info@acme.co.za",
                        "url": "https://www.acme.co.za/",
                    }
                )

            sources_cfg = {
                "input": {
                    "required_any": ["company_name"],
                    "schema_aliases": {
                        "company_name": ["company", "agency"],
                        "email": ["email", "contact_email"],
                        "website": ["website", "url"],
                    },
                    "defaults": {"source": "input"},
                }
            }

            summary_path = tmp_path / "summary.json"
            summary = run_ingestion_with_sources_config(
                input_path=csv_path,
                input_format="csv",
                sources_cfg=sources_cfg,
                output_summary_path=summary_path,
            )

            self.assertTrue(Path(summary["output"]["leads_json"]).exists())
            self.assertTrue(Path(summary["output"]["leads_csv"]).exists())
            self.assertTrue(Path(summary["output"]["rejected_rows"]).exists())

            leads = json.loads(Path(summary["output"]["leads_json"]).read_text(encoding="utf-8"))
            self.assertEqual(len(leads), 1)
            self.assertEqual(leads[0]["company_name"], "Acme Realty")
            self.assertIn("enrichment_history", leads[0])
            self.assertIn("candidates", leads[0]["enrichment_history"])
            self.assertIn("decisions", leads[0]["enrichment_history"])


if __name__ == "__main__":
    unittest.main()

