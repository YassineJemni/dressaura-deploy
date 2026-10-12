from datetime import datetime
import logging
import os
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.deps import get_db

router = APIRouter(prefix="/dresses", tags=["Dresses"])
logger = logging.getLogger(__name__)

# Cloudinary credentials are supplied through Render environment variables.
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

# Local fallback is retained for development only. Production uploads go to Cloudinary.
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads" / "dresses"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _upload_image(image: UploadFile) -> tuple[str, Optional[str]]:
    """Upload to Cloudinary when configured; otherwise save locally for development."""
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    if cloud_name and api_key and api_secret:
        try:
            result = cloudinary.uploader.upload(
                image.file,
                folder="dressaura/dresses",
                resource_type="image",
            )
            return result["secure_url"], result.get("public_id")
        except Exception as exc:
            logger.exception("Cloudinary upload failed")
            raise HTTPException(status_code=502, detail="Image upload failed. Please try again.") from exc

    # Local fallback makes local development work without Cloudinary credentials.
    if not image.filename:
        raise HTTPException(status_code=400, detail="Invalid image filename.")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_filename = os.path.basename(image.filename)
    filename = f"{timestamp}_{safe_filename}"
    file_path = UPLOAD_DIR / filename
    try:
        image.file.seek(0)
        with file_path.open("wb") as output:
            while chunk := image.file.read(1024 * 1024):
                output.write(chunk)
    except OSError as exc:
        logger.exception("Local image save failed")
        raise HTTPException(status_code=500, detail="Image could not be saved.") from exc
    return f"/uploads/dresses/{filename}", None


def _cloudinary_public_id(image_url: Optional[str]) -> Optional[str]:
    """Extract a Cloudinary public ID from a standard secure URL."""
    if not image_url:
        return None
    try:
        parsed_url = urlparse(image_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "res.cloudinary.com"
        ):
            return None
        path = parsed_url.path
        marker = "/upload/"
        if marker not in path:
            return None
        asset_path = path.split(marker, 1)[1]
        # The app's Cloudinary folder lets us ignore delivery transformations.
        folder_marker = "dressaura/dresses/"
        if folder_marker in asset_path:
            asset_path = asset_path.split(folder_marker, 1)[1]
            asset_path = f"dressaura/dresses/{asset_path}"
        # Remove optional version segment (v123456789/).
        asset_path = re.sub(r"^v\d+/", "", asset_path)
        # Remove the file extension, preserving dots inside folder/file names as much as possible.
        asset_path = re.sub(r"\.[A-Za-z0-9]+$", "", asset_path)
        return asset_path or None
    except (ValueError, IndexError):
        return None


def _delete_stored_image(image_url: Optional[str]) -> None:
    if not image_url:
        return
    public_id = _cloudinary_public_id(image_url)
    if public_id:
        try:
            cloudinary.uploader.destroy(public_id, resource_type="image")
        except Exception:
            # Keep database changes intact; log cleanup failure for later investigation.
            logger.exception("Unable to delete Cloudinary image %s", public_id)
        return

    # Local-development file cleanup.
    if image_url.startswith("/uploads/dresses/"):
        filename = os.path.basename(image_url)
        file_path = UPLOAD_DIR / filename
        try:
            if file_path.is_file():
                file_path.unlink()
        except OSError:
            logger.exception("Unable to remove local dress image %s", file_path)


def _delete_stored_image_if_unreferenced(
    db: Session,
    image_url: Optional[str],
) -> None:
    if not image_url:
        return
    public_id = _cloudinary_public_id(image_url)
    if public_id:
        referenced_urls = [
            row[0]
            for row in db.query(models.DressImage.image_url)
            .filter(models.DressImage.image_url.like("%res.cloudinary.com%"))
            .all()
        ]
        referenced_urls.extend(
            row[0]
            for row in db.query(models.Dress.image_url)
            .filter(models.Dress.image_url.like("%res.cloudinary.com%"))
            .all()
        )
        if any(
            _cloudinary_public_id(reference) == public_id
            for reference in referenced_urls
        ):
            return
    else:
        image_reference = (
            db.query(models.DressImage.id)
            .filter(models.DressImage.image_url == image_url)
            .first()
        )
        cover_reference = (
            db.query(models.Dress.id)
            .filter(models.Dress.image_url == image_url)
            .first()
        )
        if image_reference or cover_reference:
            return
    _delete_stored_image(image_url)


@router.get("/", response_model=list[schemas.DressOut])
def list_dresses(
    db: Session = Depends(get_db),
    size: Optional[str] = Query(None),
    condition: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
):
    query = db.query(models.Dress).filter(models.Dress.is_sold == False)  # noqa: E712
    if size:
        query = query.filter(models.Dress.size == size)
    if condition:
        query = query.filter(models.Dress.condition_status == condition)
    if min_price is not None:
        query = query.filter(models.Dress.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Dress.price <= max_price)
    if search:
        query = query.filter(models.Dress.brand.ilike(f"%{search}%"))
    return query.all()


@router.get("/{dress_id}", response_model=schemas.DressOut)
def get_dress(dress_id: int, db: Session = Depends(get_db)):
    dress = db.query(models.Dress).filter(models.Dress.id == dress_id).first()
    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")
    return dress


@router.post("/", response_model=schemas.DressOut)
async def create_dress(
    brand: str = Form(...),
    size: str = Form(...),
    condition_status: str = Form(...),
    price: float = Form(...),
    description: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if images and len(images) > 10:
        raise HTTPException(status_code=400, detail="A maximum of 10 images is allowed.")
    if price <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than zero")

    new_dress = models.Dress(
        user_id=current_user.id,
        brand=brand,
        size=size,
        condition_status=condition_status,
        price=price,
        description=description,
        image_url=None,
    )
    db.add(new_dress)

    uploaded_images = []
    try:
        db.flush()
        for index, image in enumerate(images or []):
            if not image.filename:
                continue
            image_url, _public_id = _upload_image(image)
            new_image = models.DressImage(
                dress_id=new_dress.id,
                image_url=image_url,
                display_order=index,
            )
            db.add(new_image)
            uploaded_images.append(image_url)
        if uploaded_images:
            new_dress.image_url = uploaded_images[0]
        db.commit()
        db.refresh(new_dress)
        return new_dress
    except Exception:
        db.rollback()
        raise


@router.put("/{dress_id}", response_model=schemas.DressOut)
def update_dress(
    dress_id: int,
    dress_update: schemas.DressCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    dress = db.query(models.Dress).filter(models.Dress.id == dress_id).first()
    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")
    if dress.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own listing")
    if dress_update.price <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than zero")

    dress.brand = dress_update.brand
    dress.size = dress_update.size
    dress.condition_status = dress_update.condition_status
    dress.price = dress_update.price
    dress.description = dress_update.description
    db.commit()
    db.refresh(dress)
    return dress


@router.post("/{dress_id}/images")
async def add_dress_images(
    dress_id: int,
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    dress = db.query(models.Dress).filter(models.Dress.id == dress_id).first()
    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")
    if dress.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own listing")
    if not images:
        raise HTTPException(status_code=400, detail="No images provided.")

    existing_images = (
        db.query(models.DressImage)
        .filter(models.DressImage.dress_id == dress_id)
        .order_by(models.DressImage.display_order)
        .all()
    )
    current_count = len(existing_images)
    if current_count + len(images) > 10:
        raise HTTPException(status_code=400, detail="A maximum of 10 images is allowed.")

    uploaded_image_urls = []
    try:
        for index, image in enumerate(images):
            if not image.filename:
                continue
            image_url, _public_id = _upload_image(image)
            uploaded_image_urls.append(image_url)
            db.add(models.DressImage(
                dress_id=dress_id,
                image_url=image_url,
                display_order=current_count + index,
            ))
        if current_count == 0 and uploaded_image_urls:
            dress.image_url = uploaded_image_urls[0]
        db.commit()
    except Exception:
        db.rollback()
        raise

    all_images = (
        db.query(models.DressImage)
        .filter(models.DressImage.dress_id == dress_id)
        .order_by(models.DressImage.display_order)
        .all()
    )
    return {"message": "Images added successfully", "count": len(all_images)}


@router.delete("/images/{image_id}")
def delete_dress_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    image = db.query(models.DressImage).filter(models.DressImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    dress = db.query(models.Dress).filter(models.Dress.id == image.dress_id).first()
    if not dress:
        raise HTTPException(status_code=404, detail="Listing not found")
    if dress.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own listing")

    dress_id = image.dress_id
    image_url = image.image_url
    db.delete(image)

    remaining_images = (
        db.query(models.DressImage)
        .filter(models.DressImage.dress_id == dress_id)
        .order_by(models.DressImage.display_order)
        .all()
    )
    for index, remaining_image in enumerate(remaining_images):
        remaining_image.display_order = index
    dress = db.query(models.Dress).filter(models.Dress.id == dress_id).first()
    if dress:
        dress.image_url = remaining_images[0].image_url if remaining_images else None
    db.commit()
    _delete_stored_image_if_unreferenced(db, image_url)
    return {"message": "Image deleted successfully"}


@router.put("/{dress_id}/images/reorder")
def reorder_dress_images(
    dress_id: int,
    reorder_data: schemas.ImageReorderRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    image_ids = reorder_data.image_ids
    dress = db.query(models.Dress).filter(models.Dress.id == dress_id).first()
    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")
    if dress.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own listing")

    images = db.query(models.DressImage).filter(models.DressImage.dress_id == dress_id).all()
    image_map = {image.id: image for image in images}
    for image_id in image_ids:
        if image_id not in image_map:
            raise HTTPException(status_code=400, detail="Invalid image ID for this dress.")
    if len(image_ids) != len(images):
        raise HTTPException(status_code=400, detail="All existing images must be included when reordering.")

    for index, image_id in enumerate(image_ids):
        image_map[image_id].display_order = index
    if image_ids:
        dress.image_url = image_map[image_ids[0]].image_url
    db.commit()
    return {"message": "Images reordered successfully"}


@router.delete("/{dress_id}")
def delete_dress(
    dress_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    dress = db.query(models.Dress).filter(models.Dress.id == dress_id).first()
    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")
    if dress.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own listing")

    # Mark as sold, matching the app's existing behavior (do not hard-delete listing).
    dress.is_sold = True
    db.commit()
    db.refresh(dress)
    return {"message": "Listing removed successfully"}
