import argparse
import hashlib
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit

import cloudinary
import cloudinary.api
import cloudinary.uploader
from cloudinary.exceptions import NotFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "app" / "uploads" / "dresses"
DEFAULT_BACKEND_ORIGIN = "https://dressaura-deploy.onrender.com"


@dataclass(frozen=True)
class ImageReference:
    table: Literal["dress", "dress_image"]
    row_id: int
    image_url: str


def is_cloudinary_url(image_url: str | None) -> bool:
    if not image_url:
        return False
    try:
        parsed = urlsplit(image_url)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "res.cloudinary.com"
        and "/image/upload/" in parsed.path
    )


def legacy_file_for_url(
    image_url: str,
    uploads_dir: Path = UPLOAD_DIR,
    backend_origin: str | None = None,
) -> Path | None:
    try:
        parsed = urlsplit(image_url.strip())
    except ValueError:
        return None

    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc:
        allowed_hosts = {
            urlsplit(backend_origin or os.getenv("BACKEND_ORIGIN", DEFAULT_BACKEND_ORIGIN)).hostname,
            "localhost",
            "127.0.0.1",
        }
        if parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
            return None

    path = unquote(parsed.path)
    if not path.startswith("/"):
        path = f"/{path}"
    prefix = "/uploads/dresses/"
    if not path.startswith(prefix):
        return None

    filename = path[len(prefix):]
    if (
        not filename
        or "/" in filename
        or "\\" in filename
        or Path(filename).name != filename
        or filename in {".", ".."}
    ):
        return None

    root = uploads_dir.resolve()
    file_path = (root / filename).resolve()
    if root not in file_path.parents:
        return None
    return file_path


def collect_image_references(db: Session) -> list[ImageReference]:
    references = [
        ImageReference("dress", row_id, image_url)
        for row_id, image_url in db.query(
            models.Dress.id,
            models.Dress.image_url,
        ).filter(models.Dress.image_url.isnot(None)).all()
    ]
    references.extend(
        ImageReference("dress_image", row_id, image_url)
        for row_id, image_url in db.query(
            models.DressImage.id,
            models.DressImage.image_url,
        ).all()
    )
    return references


def _file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cloudinary_url_for_file(
    file_path: Path,
    file_hash: str,
    uploader=cloudinary.uploader,
    cloudinary_api=cloudinary.api,
) -> str:
    public_id = f"dressaura/dresses/legacy_migration/{file_hash}"
    try:
        result = cloudinary_api.resource(public_id, resource_type="image")
    except NotFound:
        result = uploader.upload(
            str(file_path),
            public_id=public_id,
            resource_type="image",
            overwrite=False,
            unique_filename=False,
        )

    secure_url = result.get("secure_url")
    if not is_cloudinary_url(secure_url):
        raise ValueError("Cloudinary did not return a valid secure image URL.")
    return secure_url


def _error_category(error: Exception) -> str:
    if isinstance(error, SQLAlchemyError):
        return "database_error"
    if isinstance(error, OSError):
        return "local_file_error"
    if isinstance(error, ValueError):
        return "invalid_cloudinary_response"
    if isinstance(error, cloudinary.exceptions.Error):
        return "cloudinary_error"
    return "migration_error"


def _reference_summary(reference: ImageReference) -> dict:
    return {"table": reference.table, "row_id": reference.row_id}


def migrate_legacy_images(
    db: Session,
    uploads_dir: Path = UPLOAD_DIR,
    backend_origin: str | None = None,
    apply: bool = False,
    uploader=cloudinary.uploader,
    cloudinary_api=cloudinary.api,
) -> dict:
    report = {
        "migrated": 0,
        "eligible": 0,
        "skipped": {
            "already_cloudinary": 0,
            "not_supported_legacy_url": 0,
        },
        "unrecoverable": [],
        "concurrency_conflicts": [],
        "failures": [],
        "dry_run": not apply,
    }
    files_to_references: dict[Path, list[ImageReference]] = defaultdict(list)

    for reference in collect_image_references(db):
        if is_cloudinary_url(reference.image_url):
            report["skipped"]["already_cloudinary"] += 1
            continue

        file_path = legacy_file_for_url(
            reference.image_url,
            uploads_dir=uploads_dir,
            backend_origin=backend_origin,
        )
        if file_path is None:
            report["skipped"]["not_supported_legacy_url"] += 1
            continue
        if not file_path.is_file():
            report["unrecoverable"].append(
                {
                    **_reference_summary(reference),
                    "file": file_path.name,
                }
            )
            continue
        files_to_references[file_path].append(reference)

    for file_path, references in files_to_references.items():
        report["eligible"] += len(references)
        if not apply:
            continue

        conflicts = []
        try:
            file_hash = _file_sha256(file_path)
            cloudinary_url = _cloudinary_url_for_file(
                file_path,
                file_hash,
                uploader=uploader,
                cloudinary_api=cloudinary_api,
            )
            updated = 0
            for reference in references:
                model = (
                    models.Dress
                    if reference.table == "dress"
                    else models.DressImage
                )
                affected_rows = (
                    db.query(model)
                    .filter(
                        model.id == reference.row_id,
                        model.image_url == reference.image_url,
                    )
                    .update(
                        {model.image_url: cloudinary_url},
                        synchronize_session=False,
                    )
                )
                if affected_rows == 1:
                    updated += 1
                else:
                    conflicts.append(_reference_summary(reference))

            db.commit()
            db.expire_all()
            report["migrated"] += updated
            report["concurrency_conflicts"].extend(conflicts)
        except Exception as exc:
            db.rollback()
            report["failures"].append(
                {
                    "file": file_path.name,
                    "references": [
                        _reference_summary(reference) for reference in references
                    ],
                    "error_category": _error_category(exc),
                }
            )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate recoverable legacy dress photos to Cloudinary."
    )
    parser.add_argument(
        "--uploads-dir",
        type=Path,
        default=UPLOAD_DIR,
        help="Directory containing legacy app/uploads/dresses files.",
    )
    parser.add_argument(
        "--backend-origin",
        default=os.getenv("BACKEND_ORIGIN", DEFAULT_BACKEND_ORIGIN),
        help="Backend origin used by absolute legacy /uploads URLs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly request the default read-only report (no uploads or writes).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Upload recoverable images and update database URLs.",
    )
    args = parser.parse_args()

    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run conflict; choose exactly one.")

    if args.apply:
        credentials = (
            os.getenv("CLOUDINARY_CLOUD_NAME"),
            os.getenv("CLOUDINARY_API_KEY"),
            os.getenv("CLOUDINARY_API_SECRET"),
        )
        if not all(credentials):
            parser.error(
                "Cloudinary credentials must be configured for a non-dry-run migration."
            )
        cloudinary.config(
            cloud_name=credentials[0],
            api_key=credentials[1],
            api_secret=credentials[2],
            secure=True,
        )

    try:
        with SessionLocal() as db:
            report = migrate_legacy_images(
                db,
                uploads_dir=args.uploads_dir,
                backend_origin=args.backend_origin,
                apply=args.apply,
            )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "failures": [
                        {
                            "error_category": _error_category(exc),
                        }
                    ],
                    "dry_run": not args.apply,
                },
                indent=2,
            )
        )
        return 1

    print(json.dumps(report, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
