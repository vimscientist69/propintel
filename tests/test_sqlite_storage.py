import tempfile
import unittest
from pathlib import Path

from backend.core.storage_sqlite import (
    activate_settings_profile,
    claim_next_pending_batch,
    create_job_batches,
    create_job,
    delete_settings_profile,
    get_active_settings_profile,
    get_job,
    get_leads,
    init_db,
    insert_leads,
    list_job_batches,
    list_settings_profiles,
    reset_resumable_batches,
    summarize_job_batches,
    update_job_batch_status,
    list_jobs,
    upsert_settings_profile,
    update_job_completed,
    update_job_failed,
    update_job_processing_started,
    update_job_terminated,
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

    def test_job_terminated_sets_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "propintel.sqlite"
            init_db(db_path)
            create_job(db_path, job_id="job-3", input_format="csv", status="uploaded")
            update_job_processing_started(db_path, job_id="job-3")
            update_job_terminated(db_path, job_id="job-3")
            job = get_job(db_path, job_id="job-3")
            self.assertIsNotNone(job)
            self.assertEqual(job["status"], "terminated")
            self.assertEqual(job["error"], "terminated_by_user")

    def test_list_jobs_pagination_and_status_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "propintel.sqlite"
            init_db(db_path)
            create_job(db_path, job_id="job-1", input_format="csv", status="uploaded")
            create_job(db_path, job_id="job-2", input_format="json", status="uploaded")
            create_job(db_path, job_id="job-3", input_format="csv", status="uploaded")
            update_job_processing_started(db_path, job_id="job-1")
            update_job_completed(
                db_path,
                job_id="job-1",
                counts={"mapped_valid_rows": 1},
                rejected_rows=[],
            )
            update_job_failed(db_path, job_id="job-2", error="timeout")
            update_job_processing_started(db_path, job_id="job-3")

            first_page, total = list_jobs(db_path, limit=2, offset=0)
            self.assertEqual(total, 3)
            self.assertEqual(len(first_page), 2)
            self.assertEqual(first_page[0]["job_id"], "job-3")
            self.assertEqual(first_page[1]["job_id"], "job-2")

            second_page, total2 = list_jobs(db_path, limit=2, offset=2)
            self.assertEqual(total2, 3)
            self.assertEqual(len(second_page), 1)
            self.assertEqual(second_page[0]["job_id"], "job-1")

            failed_only, failed_total = list_jobs(db_path, limit=10, offset=0, status="failed")
            self.assertEqual(failed_total, 1)
            self.assertEqual(len(failed_only), 1)
            self.assertEqual(failed_only[0]["job_id"], "job-2")
            self.assertEqual(failed_only[0]["error"], "timeout")

    def test_settings_profiles_upsert_activate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "propintel.sqlite"
            init_db(db_path)
            upsert_settings_profile(
                db_path,
                name="profile-a",
                payload={"website": {"enabled": True}},
                activate=True,
            )
            active = get_active_settings_profile(db_path)
            self.assertIsNotNone(active)
            self.assertEqual(active["name"], "profile-a")

            upsert_settings_profile(
                db_path,
                name="profile-b",
                payload={"scoring": {"enabled": True}},
                activate=False,
            )
            profiles = list_settings_profiles(db_path)
            self.assertEqual(len(profiles), 2)
            self.assertTrue(activate_settings_profile(db_path, name="profile-b"))
            active2 = get_active_settings_profile(db_path)
            self.assertIsNotNone(active2)
            self.assertEqual(active2["name"], "profile-b")
            self.assertTrue(delete_settings_profile(db_path, name="profile-a"))
            profiles_after = list_settings_profiles(db_path)
            self.assertEqual(len(profiles_after), 1)

    def test_job_batches_lifecycle_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "propintel.sqlite"
            init_db(db_path)
            create_job(db_path, job_id="job-b", input_format="csv", status="uploaded")
            create_job_batches(db_path, job_id="job-b", total_rows=230, batch_size=100)
            batches = list_job_batches(db_path, job_id="job-b")
            self.assertEqual(len(batches), 3)
            first = claim_next_pending_batch(db_path, job_id="job-b")
            self.assertIsNotNone(first)
            self.assertEqual(first["batch_index"], 0)
            update_job_batch_status(db_path, job_id="job-b", batch_index=0, status="completed", processed_rows=100)
            second = claim_next_pending_batch(db_path, job_id="job-b")
            self.assertIsNotNone(second)
            update_job_batch_status(
                db_path,
                job_id="job-b",
                batch_index=1,
                status="failed",
                processed_rows=0,
                error="api error",
            )
            summary = summarize_job_batches(db_path, job_id="job-b")
            self.assertEqual(summary["batches_total"], 3)
            self.assertEqual(summary["batches_completed"], 1)
            self.assertEqual(summary["rows_total"], 230)
            self.assertEqual(summary["rows_processed"], 100)
            self.assertEqual(summary["failed_batches"], 1)
            reset_resumable_batches(db_path, job_id="job-b")
            rows = list_job_batches(db_path, job_id="job-b")
            statuses = [row["status"] for row in rows]
            self.assertEqual(statuses.count("pending"), 2)


if __name__ == "__main__":
    unittest.main()

