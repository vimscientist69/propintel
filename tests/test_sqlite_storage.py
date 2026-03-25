import tempfile
import unittest
from pathlib import Path

from backend.core.storage_sqlite import (
    create_job,
    get_job,
    get_leads,
    init_db,
    insert_leads,
    update_job_completed,
    update_job_failed,
    update_job_processing_started,
)


class TestSqliteStorage(unittest.TestCase):
    def test_job_lifecycle_and_leads_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "propintel.sqlite"

            init_db(db_path)
            create_job(
                db_path,
                job_id="job-1",
                input_format="csv",
                status="uploaded",
            )
            job = get_job(db_path, job_id="job-1")
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "uploaded")

            update_job_processing_started(db_path, job_id="job-1")
            job = get_job(db_path, job_id="job-1")
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "processing")
            self.assertIsNotNone(job["started_at"])

            leads = [
                {"company_name": "Acme Realty", "website": "acme.co.za", "email": "info@acme.co.za"},
                {"company_name": "Beta Realty", "website": "beta.co.za", "email": "hello@beta.co.za"},
            ]
            insert_leads(db_path, job_id="job-1", leads=leads)

            counts = {"mapped_valid_rows": 2, "rejected_rows": 0, "deduped_rows": 2}
            rejected_rows = []
            update_job_completed(db_path, job_id="job-1", counts=counts, rejected_rows=rejected_rows)

            job = get_job(db_path, job_id="job-1")
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["counts"], counts)
            self.assertIsNotNone(job["completed_at"])

            stored_leads = get_leads(db_path, job_id="job-1")
            self.assertEqual(len(stored_leads), 2)
            self.assertEqual(stored_leads[0]["company_name"], "Acme Realty")

    def test_job_failed_sets_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "propintel.sqlite"
            init_db(db_path)
            create_job(db_path, job_id="job-2", input_format="csv", status="uploaded")
            update_job_failed(db_path, job_id="job-2", error="boom")
            job = get_job(db_path, job_id="job-2")
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "failed")
            self.assertEqual(job["error"], "boom")


if __name__ == "__main__":
    unittest.main()

