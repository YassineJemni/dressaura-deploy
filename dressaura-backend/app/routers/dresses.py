from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import shutil
from datetime import datetime

from app.deps import get_db
from app import models, schemas


router = APIRouter(
    prefix="/dresses",
    tags=["Dresses"]
)




UPLOAD_DIR = "app/uploads/dresses"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)




@router.get(
    "/",
    response_model=list[schemas.DressOut]
)
def list_dresses(
    db: Session = Depends(get_db),
    size: Optional[str] = Query(None),
    condition: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
):

    query = (
        db.query(models.Dress)
        .filter(
            models.Dress.is_sold == False
        )
    )

    if size:
        query = query.filter(
            models.Dress.size == size
        )

    if condition:
        query = query.filter(
            models.Dress.condition_status == condition
        )

    if min_price is not None:
        query = query.filter(
            models.Dress.price >= min_price
        )

    if max_price is not None:
        query = query.filter(
            models.Dress.price <= max_price
        )

    if search:
        query = query.filter(
            models.Dress.brand.ilike(
                f"%{search}%"
            )
        )

    dresses = query.all()

    return dresses




@router.get(
    "/{dress_id}",
    response_model=schemas.DressOut
)
def get_dress(
    dress_id: int,
    db: Session = Depends(get_db)
):

    dress = (
        db.query(models.Dress)
        .filter(
            models.Dress.id == dress_id
        )
        .first()
    )

    if not dress:
        raise HTTPException(
            status_code=404,
            detail="Dress not found"
        )

    return dress



@router.post(
    "/",
    response_model=schemas.DressOut
)
async def create_dress(
    user_id: int = Form(...),
    brand: str = Form(...),
    size: str = Form(...),
    condition_status: str = Form(...),
    price: float = Form(...),
    description: Optional[str] = Form(None),

    images: Optional[List[UploadFile]] = File(None),

    db: Session = Depends(get_db)
):



    new_dress = models.Dress(
        user_id=user_id,
        brand=brand,
        size=size,
        condition_status=condition_status,
        price=price,
        description=description,
        image_url=None
    )

    db.add(new_dress)

    db.commit()

    db.refresh(new_dress)




    uploaded_images = []

    if images:

        if len(images) > 10:
            raise HTTPException(
                status_code=400,
                detail="A maximum of 10 images is allowed."
            )

        for index, image in enumerate(images):

            if not image.filename:
                continue

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )

            safe_filename = os.path.basename(
                image.filename
            )

            filename = (
                f"{timestamp}_{index}_{safe_filename}"
            )

            file_path = os.path.join(
                UPLOAD_DIR,
                filename
            )

            with open(
                file_path,
                "wb"
            ) as buffer:

                shutil.copyfileobj(
                    image.file,
                    buffer
                )

            image_url = (
                f"/uploads/dresses/{filename}"
            )

            new_image = models.DressImage(
                dress_id=new_dress.id,
                image_url=image_url,
                display_order=index
            )

            db.add(new_image)

            uploaded_images.append(
                image_url
            )




    if uploaded_images:

        new_dress.image_url = (
            uploaded_images[0]
        )

    db.commit()

    db.refresh(new_dress)

    return new_dress




@router.put(
    "/{dress_id}",
    response_model=schemas.DressOut
)
def update_dress(
    dress_id: int,
    dress_update: schemas.DressCreate,
    db: Session = Depends(get_db)
):

    dress = (
        db.query(models.Dress)
        .filter(
            models.Dress.id == dress_id
        )
        .first()
    )

    if not dress:
        raise HTTPException(
            status_code=404,
            detail="Dress not found"
        )

    dress.brand = dress_update.brand

    dress.size = dress_update.size

    dress.condition_status = (
        dress_update.condition_status
    )

    dress.price = dress_update.price

    dress.description = (
        dress_update.description
    )

    db.commit()

    db.refresh(dress)

    return dress




@router.post(
    "/{dress_id}/images"
)
async def add_dress_images(
    dress_id: int,

    images: Optional[List[UploadFile]] = File(
        None
    ),

    db: Session = Depends(get_db)
):

    dress = (
        db.query(models.Dress)
        .filter(
            models.Dress.id == dress_id
        )
        .first()
    )

    if not dress:
        raise HTTPException(
            status_code=404,
            detail="Dress not found"
        )


    if not images:
        raise HTTPException(
            status_code=400,
            detail="No images provided."
        )




    existing_images = (
        db.query(models.DressImage)
        .filter(
            models.DressImage.dress_id
            == dress_id
        )
        .order_by(
            models.DressImage.display_order
        )
        .all()
    )

    current_count = len(
        existing_images
    )




    if current_count + len(images) > 10:

        raise HTTPException(
            status_code=400,
            detail=(
                "A maximum of 10 images is allowed."
            )
        )




    for index, image in enumerate(images):

        if not image.filename:
            continue

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        safe_filename = os.path.basename(
            image.filename
        )

        filename = (
            f"{timestamp}_"
            f"{current_count + index}_"
            f"{safe_filename}"
        )

        file_path = os.path.join(
            UPLOAD_DIR,
            filename
        )

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                image.file,
                buffer
            )

        image_url = (
            f"/uploads/dresses/{filename}"
        )

        new_image = models.DressImage(
            dress_id=dress_id,
            image_url=image_url,
            display_order=(
                current_count + index
            )
        )

        db.add(new_image)


    db.commit()




    all_images = (
        db.query(models.DressImage)
        .filter(
            models.DressImage.dress_id
            == dress_id
        )
        .order_by(
            models.DressImage.display_order
        )
        .all()
    )

    if all_images:

        dress.image_url = (
            all_images[0].image_url
        )

    db.commit()


    return {
        "message": "Images added successfully",
        "count": len(all_images)
    }




@router.delete(
    "/images/{image_id}"
)
def delete_dress_image(
    image_id: int,
    db: Session = Depends(get_db)
):

    image = (
        db.query(models.DressImage)
        .filter(
            models.DressImage.id == image_id
        )
        .first()
    )

    if not image:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )


    dress_id = image.dress_id

    image_url = image.image_url




    db.delete(image)

    db.commit()




    if image_url:

        filename = os.path.basename(
            image_url
        )

        file_path = os.path.join(
            UPLOAD_DIR,
            filename
        )

        if os.path.exists(file_path):

            try:
                os.remove(file_path)
            except OSError:
                pass



    remaining_images = (
        db.query(models.DressImage)
        .filter(
            models.DressImage.dress_id
            == dress_id
        )
        .order_by(
            models.DressImage.display_order
        )
        .all()
    )

    for index, remaining_image in enumerate(
        remaining_images
    ):

        remaining_image.display_order = index




    dress = (
        db.query(models.Dress)
        .filter(
            models.Dress.id == dress_id
        )
        .first()
    )

    if dress:

        if remaining_images:

            dress.image_url = (
                remaining_images[0].image_url
            )

        else:

            dress.image_url = None


    db.commit()


    return {
        "message": "Image deleted successfully"
    }




@router.put(
    "/{dress_id}/images/reorder"
)
def reorder_dress_images(
    dress_id: int,

    reorder_data: schemas.ImageReorderRequest,

    db: Session = Depends(get_db)
):

    image_ids = reorder_data.image_ids




    dress = (
        db.query(models.Dress)
        .filter(
            models.Dress.id == dress_id
        )
        .first()
    )

    if not dress:

        raise HTTPException(
            status_code=404,
            detail="Dress not found"
        )




    images = (
        db.query(models.DressImage)
        .filter(
            models.DressImage.dress_id
            == dress_id
        )
        .all()
    )


    image_map = {
        image.id: image
        for image in images
    }




    for image_id in image_ids:

        if image_id not in image_map:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid image ID for this dress."
                )
            )




    if len(image_ids) != len(images):

        raise HTTPException(
            status_code=400,
            detail=(
                "All existing images must be "
                "included when reordering."
            )
        )




    for index, image_id in enumerate(
        image_ids
    ):

        image_map[
            image_id
        ].display_order = index



    if image_ids:

        dress.image_url = (
            image_map[
                image_ids[0]
            ].image_url
        )


    db.commit()


    return {
        "message": "Images reordered successfully"
    }




@router.delete(
    "/{dress_id}"
)
def delete_dress(
    dress_id: int,
    db: Session = Depends(get_db)
):

    dress = (
        db.query(models.Dress)
        .filter(
            models.Dress.id == dress_id
        )
        .first()
    )

    if not dress:

        raise HTTPException(
            status_code=404,
            detail="Dress not found"
        )




    dress.is_sold = True

    db.commit()

    db.refresh(dress)


    return {
        "message": "Listing removed successfully"
    }