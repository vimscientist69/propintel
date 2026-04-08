import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

from backend.core.storage_sqlite import create_job, init_db, insert_leads, update_job_completed, update_job_failed

if TestClient is not None:
    from backend.api import jobs as jobs_module
    from backend.api.routes import app


@unittest.skipIf(TestClient is None, "fastapi not installed in test environment")
class TestApiJobs(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "propintel.sqlite"
        self.upload_dir = Path(self.tmp.name) / "uploads"
        init_db(self.db_path)

        jobs_module.DB_PATH = self.db_path
        jobs_module.UPLOAD_DIR = self.upload_dir

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_get_jobs_list_paginated(self) -> None:
        create_job(self.db_path, job_id="j1", input_format="csv", status="uploaded")
        create_job(self.db_path, job_id="j2", input_format="json", status="uploaded")
        update_job_failed(self.db_path, job_id="j2", error="boom")

        r = self.client.get("/jobs", params={"limit": 1, "offset": 0})
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["items"]), 1)

        r_failed = self.client.get("/jobs", params={"status": "failed"})
        self.assertEqual(r_failed.status_code, 200)
        payload_failed = r_failed.json()
        self.assertEqual(payload_failed["total"], 1)
        self.assertEqual(payload_failed["items"][0]["job_id"], "j2")

    def test_rejected_and_export_endpoints(self) -> None:
        create_job(self.db_path, job_id="j3", input_format="csv", status="uploaded")
        leads = [
            {
                "company_name": "Acme Realty",
                "website": "https://acme.example",
                "lead_score": 77,
            }
        ]
        insert_leads(self.db_path, job_id="j3", leads=leads)
        update_job_completed(
            self.db_path,
            job_id="j3",
            counts={"deduped_rows": 1},
            rejected_rows=[{"row_index": 1, "reason": "invalid_email"}],
        )

        r_rej = self.client.get("/jobs/j3/rejected")
        self.assertEqual(r_rej.status_code, 200)
        self.assertEqual(len(r_rej.json()["rejected_rows"]), 1)

        r_json = self.client.get("/jobs/j3/export", params={"format": "json"})
        self.assertEqual(r_json.status_code, 200)
        payload_json = r_json.json()
        self.assertEqual(len(payload_json), 1)
        self.assertEqual(payload_json[0]["company_name"], "Acme Realty")

        r_csv = self.client.get("/jobs/j3/export", params={"format": "csv"})
        self.assertEqual(r_csv.status_code, 200)
        self.assertIn("company_name", r_csv.text)
        self.assertIn("Acme Realty", r_csv.text)

    def test_export_rejects_unfinished_job(self) -> None:
        create_job(self.db_path, job_id="j4", input_format="csv", status="uploaded")
        r = self.client.get("/jobs/j4/export", params={"format": "json"})
        self.assertEqual(r.status_code, 409)

    def test_terminate_job(self) -> None:
        create_job(self.db_path, job_id="j5", input_format="csv", status="uploaded")
        r = self.client.post("/jobs/j5/terminate")
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertEqual(payload["status"], "terminated")
        status = self.client.get("/jobs/j5")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "terminated")

    def test_settings_endpoints(self) -> None:
        validate = self.client.post("/settings/validate", json={"website": {"enabled": True}})
        self.assertEqual(validate.status_code, 200)
        self.assertTrue(validate.json()["ok"])
        invalid_validate = self.client.post("/settings/validate", json={"foo": {}})
        self.assertEqual(invalid_validate.status_code, 200)
        self.assertFalse(invalid_validate.json()["ok"])
        save = self.client.put(
            "/settings",
            json={
                "name": "profile-test",
                "payload": {"website": {"enabled": True}, "scoring": {"enabled": True, "weights": {}}},
                "activate": True,
            },
        )
        self.assertEqual(save.status_code, 200)
        get_settings = self.client.get("/settings")
        self.assertEqual(get_settings.status_code, 200)
        self.assertIn("active", get_settings.json())

if __name__ == "__main__":
    unittest.main()
