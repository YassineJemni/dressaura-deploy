import os
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-only")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from cloudinary.exceptions import NotFound
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import event, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth import get_current_user
from app.database import Base
from app.deps import get_db
from app.routers import dresses as dress_routes
from scripts.migrate_legacy_images import (
    is_cloudinary_url,
    legacy_file_for_url,
    main as migration_main,
    migrate_legacy_images,
)

CLOUDINARY_URL = (
    "https://res.cloudinary.com/example/image/upload/v123/dressaura/dresses/a.jpg"
)


class DressImageRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )
        self.db = self.session_factory()
        self.user = models.User(
            name="Seller",
            email="seller@example.test",
            password="not-a-real-password",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        app = FastAPI()
        app.include_router(dress_routes.router)
        app.dependency_overrides[get_db] = self._get_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.app = app

    def tearDown(self):
        self.client.close()
        self.app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _get_db(self):
        yield self.db

    def _make_dress(self, image_url=CLOUDINARY_URL):
        dress = models.Dress(
            user_id=self.user.id,
            brand="Test dress",
            size="M",
            condition_status="Good",
            price=24.5,
            description="Test listing",
            image_url=image_url,
            is_sold=False,
        )
        self.db.add(dress)
        self.db.commit()
        self.db.refresh(dress)
        return dress

    def test_listing_and_detail_responses_keep_saved_cloudinary_urls(self):
        dress = self._make_dress()
        image = models.DressImage(
            dress_id=dress.id,
            image_url=CLOUDINARY_URL,
            display_order=0,
        )
        self.db.add(image)
        self.db.commit()

        list_response = self.client.get("/dresses/")
        detail_response = self.client.get(f"/dresses/{dress.id}")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        for data in (list_response.json()[0], detail_response.json()):
            self.assertEqual(data["image_url"], CLOUDINARY_URL)
            self.assertEqual(data["images"][0]["image_url"], CLOUDINARY_URL)

    def test_create_persists_cloudinary_urls_in_both_image_fields(self):
        with patch.object(
            dress_routes,
            "_upload_image",
            return_value=(CLOUDINARY_URL, "dressaura/dresses/a"),
        ):
            response = self.client.post(
                "/dresses/",
                data={
                    "brand": "New dress",
                    "size": "S",
                    "condition_status": "New",
                    "price": "30",
                },
                files=[("images", ("dress.jpg", b"image-bytes", "image/jpeg"))],
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["image_url"], CLOUDINARY_URL)
        self.assertEqual(data["images"][0]["image_url"], CLOUDINARY_URL)

    def test_failed_cloudinary_upload_does_not_change_existing_listing(self):
        dress = self._make_dress()
        self.db.add(
            models.DressImage(
                dress_id=dress.id,
                image_url=CLOUDINARY_URL,
                display_order=0,
            )
        )
        self.db.commit()

        with patch.object(
            dress_routes,
            "_upload_image",
            side_effect=HTTPException(
                status_code=502,
                detail="simulated Cloudinary failure",
            ),
        ):
            response = self.client.post(
                f"/dresses/{dress.id}/images",
                files=[("images", ("new.jpg", b"new-image", "image/jpeg"))],
            )

        self.assertEqual(response.status_code, 502)
        self.db.expire_all()
        saved_dress = self.db.get(models.Dress, dress.id)
        saved_images = (
            self.db.query(models.DressImage)
            .filter(models.DressImage.dress_id == dress.id)
            .all()
        )
        self.assertEqual(saved_dress.image_url, CLOUDINARY_URL)
        self.assertEqual([image.image_url for image in saved_images], [CLOUDINARY_URL])

    def test_shared_cloudinary_asset_is_not_deleted_when_one_reference_is_removed(self):
        dress = self._make_dress()
        image = models.DressImage(
            dress_id=dress.id,
            image_url=CLOUDINARY_URL,
            display_order=0,
        )
        other_dress = self._make_dress()
        other_dress.image_url = f"{CLOUDINARY_URL}?source=cover"
        self.db.add(image)
        self.db.add(
            models.DressImage(
                dress_id=other_dress.id,
                image_url=f"{CLOUDINARY_URL}?source=thumbnail",
                display_order=0,
            )
        )
        self.db.add(
            models.DressImage(
                dress_id=other_dress.id,
                image_url=(
                    "https://res.cloudinary.com/example/image/upload/"
                    "c_fill,w_200/v999/dressaura/dresses/a.jpg"
                ),
                display_order=1,
            )
        )
        self.db.commit()

        with patch.object(dress_routes, "_delete_stored_image") as delete_image:
            response = self.client.delete(f"/dresses/images/{image.id}")

        self.assertEqual(response.status_code, 200)
        delete_image.assert_not_called()


class LegacyImageMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.user = models.User(
            name="Seller",
            email="migration@example.test",
            password="not-a-real-password",
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.uploads_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _make_dress(self, image_url):
        dress = models.Dress(
            user_id=self.user.id,
            brand="Legacy dress",
            size="M",
            condition_status="Good",
            price=20,
            image_url=image_url,
            is_sold=False,
        )
        self.db.add(dress)
        self.db.commit()
        self.db.refresh(dress)
        return dress

    def test_cloudinary_and_supported_legacy_url_detection(self):
        image_path = self.uploads_dir / "legacy dress.jpg"
        image_path.write_bytes(b"image-data")

        self.assertTrue(is_cloudinary_url(CLOUDINARY_URL))
        self.assertFalse(is_cloudinary_url("/uploads/dresses/legacy dress.jpg"))
        self.assertEqual(
            legacy_file_for_url(
                "/uploads/dresses/legacy%20dress.jpg",
                uploads_dir=self.uploads_dir,
            ),
            image_path,
        )
        self.assertEqual(
            legacy_file_for_url(
                "https://dressaura-deploy.onrender.com/uploads/dresses/legacy%20dress.jpg",
                uploads_dir=self.uploads_dir,
            ),
            image_path,
        )
        self.assertIsNone(
            legacy_file_for_url(
                "https://other.example/uploads/dresses/legacy%20dress.jpg",
                uploads_dir=self.uploads_dir,
            )
        )
        self.assertIsNone(
            legacy_file_for_url(
                "/uploads/dresses/../secret.jpg",
                uploads_dir=self.uploads_dir,
            )
        )

    def test_migrates_each_column_and_skips_cloudinary_rows_on_rerun(self):
        image_path = self.uploads_dir / "legacy.jpg"
        image_path.write_bytes(b"recoverable-image")
        legacy_path = "/uploads/dresses/legacy.jpg"
        dress = self._make_dress(legacy_path)
        cloudinary_dress = self._make_dress(CLOUDINARY_URL)
        dress_image = models.DressImage(
            dress_id=dress.id,
            image_url=legacy_path,
            display_order=0,
        )
        self.db.add(dress_image)
        self.db.commit()

        uploader = Mock(
            upload=Mock(
                return_value={
                    "secure_url": CLOUDINARY_URL,
                    "public_id": "dressaura/dresses/legacy",
                }
            )
        )
        cloudinary_api = Mock()
        cloudinary_api.resource.side_effect = NotFound("not found")

        report = migrate_legacy_images(
            self.db,
            uploads_dir=self.uploads_dir,
            apply=True,
            uploader=uploader,
            cloudinary_api=cloudinary_api,
        )

        self.db.expire_all()
        self.assertEqual(report["migrated"], 2)
        self.assertEqual(report["skipped"]["already_cloudinary"], 1)
        self.assertEqual(self.db.get(models.Dress, dress.id).image_url, CLOUDINARY_URL)
        self.assertEqual(
            self.db.get(models.DressImage, dress_image.id).image_url,
            CLOUDINARY_URL,
        )
        self.assertEqual(
            self.db.get(models.DressImage, dress_image.id).display_order,
            0,
        )
        self.assertEqual(
            self.db.get(models.Dress, cloudinary_dress.id).image_url,
            CLOUDINARY_URL,
        )
        uploader.upload.assert_called_once()

        rerun = migrate_legacy_images(
            self.db,
            uploads_dir=self.uploads_dir,
            apply=True,
            uploader=uploader,
            cloudinary_api=cloudinary_api,
        )
        self.assertEqual(rerun["migrated"], 0)
        self.assertEqual(rerun["skipped"]["already_cloudinary"], 3)
        uploader.upload.assert_called_once()

    def test_reuses_hash_addressed_cloudinary_asset_after_interrupted_run(self):
        image_path = self.uploads_dir / "previously-uploaded.jpg"
        image_path.write_bytes(b"previously-uploaded-image")
        dress = self._make_dress("/uploads/dresses/previously-uploaded.jpg")
        uploader = Mock()
        cloudinary_api = Mock(
            resource=Mock(return_value={"secure_url": CLOUDINARY_URL})
        )

        report = migrate_legacy_images(
            self.db,
            uploads_dir=self.uploads_dir,
            apply=True,
            uploader=uploader,
            cloudinary_api=cloudinary_api,
        )

        self.assertEqual(report["migrated"], 1)
        self.assertEqual(
            self.db.get(models.Dress, dress.id).image_url,
            CLOUDINARY_URL,
        )
        uploader.upload.assert_not_called()

    def test_missing_files_are_reported_and_failed_uploads_leave_urls_unchanged(self):
        missing_dress = self._make_dress("/uploads/dresses/missing.jpg")
        image_path = self.uploads_dir / "present.jpg"
        image_path.write_bytes(b"recoverable-image")
        failing_dress = self._make_dress("/uploads/dresses/present.jpg")
        uploader = Mock(upload=Mock(side_effect=RuntimeError("upload failed")))
        cloudinary_api = Mock()
        cloudinary_api.resource.side_effect = NotFound("not found")

        report = migrate_legacy_images(
            self.db,
            uploads_dir=self.uploads_dir,
            apply=True,
            uploader=uploader,
            cloudinary_api=cloudinary_api,
        )

        self.db.expire_all()
        self.assertEqual(len(report["unrecoverable"]), 1)
        self.assertEqual(len(report["failures"]), 1)
        self.assertEqual(
            self.db.get(models.Dress, missing_dress.id).image_url,
            "/uploads/dresses/missing.jpg",
        )
        self.assertEqual(
            self.db.get(models.Dress, failing_dress.id).image_url,
            "/uploads/dresses/present.jpg",
        )

    def test_default_and_explicit_dry_runs_perform_no_writes_or_uploads(self):
        image_path = self.uploads_dir / "legacy.jpg"
        image_path.write_bytes(b"recoverable-image")
        dress = self._make_dress("/uploads/dresses/legacy.jpg")
        statements = []
        module = sys.modules["scripts.migrate_legacy_images"]

        def record_statement(
            _connection,
            _cursor,
            statement,
            _parameters,
            _context,
            _many,
        ):
            statements.append(statement.lstrip().split(" ", 1)[0].upper())

        event.listen(self.engine, "before_cursor_execute", record_statement)
        try:
            with (
                patch.object(module.cloudinary.uploader, "upload") as upload,
                patch.object(module.cloudinary.api, "resource") as resource,
                patch.object(module.cloudinary, "config") as config,
            ):
                for args in ([], ["--dry-run"]):
                    output = io.StringIO()
                    with (
                        patch.object(
                            sys,
                            "argv",
                            [
                                "migrate_legacy_images",
                                "--uploads-dir",
                                str(self.uploads_dir),
                                *args,
                            ],
                        ),
                        patch.object(module, "SessionLocal", return_value=self.db),
                        patch.dict(
                            os.environ,
                            {
                                "CLOUDINARY_CLOUD_NAME": "test-cloud",
                                "CLOUDINARY_API_KEY": "test-key",
                                "CLOUDINARY_API_SECRET": "test-secret",
                            },
                        ),
                        contextlib.redirect_stdout(output),
                    ):
                        self.assertEqual(migration_main(), 0)

                    report = json.loads(output.getvalue())
                    self.assertTrue(report["dry_run"])
                    self.assertEqual(report["eligible"], 1)

                upload.assert_not_called()
                resource.assert_not_called()
                config.assert_not_called()
            self.assertNotIn("UPDATE", statements)
            self.assertNotIn("INSERT", statements)
            self.assertNotIn("DELETE", statements)
            self.assertEqual(
                self.db.get(models.Dress, dress.id).image_url,
                "/uploads/dresses/legacy.jpg",
            )
        finally:
            event.remove(self.engine, "before_cursor_execute", record_statement)

    def test_conflicting_flags_are_rejected_before_opening_a_database(self):
        stderr = io.StringIO()
        session_factory = Mock(side_effect=AssertionError("DB must not be opened"))
        with (
            patch.object(sys, "argv", ["migrate_legacy_images", "--apply", "--dry-run"]),
            patch(
                "scripts.migrate_legacy_images.SessionLocal",
                session_factory,
            ),
            contextlib.redirect_stderr(stderr),
        ):
            with self.assertRaises(SystemExit) as exit_info:
                migration_main()

        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("--apply and --dry-run conflict", stderr.getvalue())
        session_factory.assert_not_called()

    def test_apply_flag_enables_live_mode_explicitly(self):
        module = sys.modules["scripts.migrate_legacy_images"]
        report = {
            "migrated": 0,
            "eligible": 0,
            "skipped": {},
            "unrecoverable": [],
            "concurrency_conflicts": [],
            "failures": [],
            "dry_run": False,
        }
        with (
            patch.object(sys, "argv", ["migrate_legacy_images", "--apply"]),
            patch.object(module, "SessionLocal", return_value=self.db),
            patch.object(module, "migrate_legacy_images", return_value=report) as migrate,
            patch.object(module.cloudinary, "config") as config,
            patch.dict(
                os.environ,
                {
                    "CLOUDINARY_CLOUD_NAME": "test-cloud",
                    "CLOUDINARY_API_KEY": "test-key",
                    "CLOUDINARY_API_SECRET": "test-secret",
                },
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(migration_main(), 0)

        config.assert_called_once()
        self.assertIs(migrate.call_args.kwargs["apply"], True)

    def test_conditional_updates_skip_concurrently_changed_rows_in_both_models(self):
        image_path = self.uploads_dir / "legacy.jpg"
        image_path.write_bytes(b"recoverable-image")
        legacy_path = "/uploads/dresses/legacy.jpg"
        dress = self._make_dress(legacy_path)
        image = models.DressImage(
            dress_id=dress.id,
            image_url=legacy_path,
            display_order=0,
        )
        self.db.add(image)
        self.db.commit()
        concurrent_dress_url = f"{CLOUDINARY_URL}?updated=concurrently"
        concurrent_image_url = f"{CLOUDINARY_URL}?image=concurrently"

        def upload_after_concurrent_change(*_args, **_kwargs):
            self.db.execute(
                update(models.Dress)
                .where(models.Dress.id == dress.id)
                .values(image_url=concurrent_dress_url)
            )
            self.db.execute(
                update(models.DressImage)
                .where(models.DressImage.id == image.id)
                .values(image_url=concurrent_image_url)
            )
            self.db.commit()
            return CLOUDINARY_URL

        with patch(
            "scripts.migrate_legacy_images._cloudinary_url_for_file",
            side_effect=upload_after_concurrent_change,
        ):
            report = migrate_legacy_images(
                self.db,
                uploads_dir=self.uploads_dir,
                apply=True,
            )

        self.assertEqual(report["migrated"], 0)
        self.assertEqual(
            report["concurrency_conflicts"],
            [
                {"table": "dress", "row_id": dress.id},
                {"table": "dress_image", "row_id": image.id},
            ],
        )
        self.assertEqual(
            self.db.get(models.Dress, dress.id).image_url,
            concurrent_dress_url,
        )
        self.assertEqual(
            self.db.get(models.DressImage, image.id).image_url,
            concurrent_image_url,
        )
        self.assertEqual(self.db.get(models.DressImage, image.id).display_order, 0)

    def test_report_does_not_expose_exception_text_urls_or_secrets(self):
        image_path = self.uploads_dir / "legacy.jpg"
        image_path.write_bytes(b"recoverable-image")
        original_url = (
            "/uploads/dresses/legacy.jpg?signature=SIGNED_URL_SECRET"
        )
        dress = self._make_dress(original_url)
        secret_text = "API_SECRET_VALUE https://service/?token=SIGNED_TOKEN"
        uploader = Mock(upload=Mock(side_effect=RuntimeError(secret_text)))
        cloudinary_api = Mock()
        cloudinary_api.resource.side_effect = NotFound("not found")

        report = migrate_legacy_images(
            self.db,
            uploads_dir=self.uploads_dir,
            apply=True,
            uploader=uploader,
            cloudinary_api=cloudinary_api,
        )
        output = json.dumps(report)

        self.assertEqual(report["failures"][0]["error_category"], "migration_error")
        self.assertNotIn(secret_text, output)
        self.assertNotIn("SIGNED_URL_SECRET", output)
        self.assertNotIn("SIGNED_TOKEN", output)
        self.assertNotIn(original_url, output)
        self.assertEqual(
            self.db.get(models.Dress, dress.id).image_url,
            original_url,
        )

    def test_cli_sanitizes_unhandled_external_error_without_traceback(self):
        module = sys.modules["scripts.migrate_legacy_images"]
        secret_message = "DB_PASSWORD=hidden SIGNED_URL_TOKEN=private"
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["migrate_legacy_images"]),
            patch.object(
                module,
                "SessionLocal",
                side_effect=RuntimeError(secret_message),
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(migration_main(), 1)

        text = output.getvalue()
        report = json.loads(text)
        self.assertEqual(
            report["failures"][0]["error_category"],
            "migration_error",
        )
        self.assertNotIn(secret_message, text)
        self.assertNotIn("Traceback", text)


if __name__ == "__main__":
    unittest.main()
