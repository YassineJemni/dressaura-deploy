from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import Order, Dress, User
import random

router = APIRouter(prefix="/orders", tags=["orders"])


ALLOWED_DELIVERY_COMPANIES = {
    "DPD": "DPD Pickup Point",
    "GLS": "GLS ParcelShop",
    "Packeta": "Packeta Pickup Point",
}

DELIVERY_STATUSES = [
    "Awaiting Drop-off",
    "Dropped Off",
    "In Transit",
    "Out for Delivery",
    "Delivered",
]


def generate_tracking_number():
    """
    Generates a simulated Dressaura tracking number.
    Example: DRS-482913
    """
    return f"DRS-{random.randint(100000, 999999)}"


def get_dropoff_location(delivery_company: str):
    """
    Returns a simulated drop-off location based
    on the selected delivery company.
    """
    return ALLOWED_DELIVERY_COMPANIES.get(
        delivery_company,
        "Pickup Point"
    )




@router.post("/")
def create_order(
    user_id: int,
    dress_id: int,
    payment_method: str,
    delivery_company: str,
    order_price: float,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new order and initializes the simulated
    delivery process.
    """

    # Find the dress
    dress = (
        db.query(Dress)
        .filter(Dress.id == dress_id)
        .first()
    )

    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")

    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot place an order for another user")

    if dress.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot buy your own listing")

    # Prevent purchasing an already sold dress
    if dress.is_sold:
        raise HTTPException(status_code=409, detail="Dress already sold")

    # Validate delivery company
    if delivery_company not in ALLOWED_DELIVERY_COMPANIES:
        raise HTTPException(
            status_code=400,
            detail="Invalid delivery company. Choose DPD, GLS, or Packeta.",
        )

    # Validate order price
    if order_price <= 0:
        raise HTTPException(status_code=400, detail="Invalid order price")
    if dress.price <= 0:
        raise HTTPException(status_code=400, detail="Listing price must be greater than zero")

    # Generate simulated tracking information
    tracking_number = generate_tracking_number()

    dropoff_location = get_dropoff_location(
        delivery_company
    )

    # Create order
    order = Order(
        user_id=user_id,
        dress_id=dress_id,
        order_price=float(dress.price),
        payment_method=payment_method,
        status="in-progress",
        delivery_company=delivery_company,
        delivery_status="Awaiting Drop-off",
        tracking_number=tracking_number,
        dropoff_location=dropoff_location,
    )

    db.add(order)
    dress.is_sold = True
    db.commit()
    db.refresh(order)

    return {
        "message": "Order created successfully",
        "order_id": order.id,
        "dress_id": dress.id,
        "order_price": float(order.order_price),
        "payment_method": order.payment_method,
        "delivery_company": order.delivery_company,
        "delivery_status": order.delivery_status,
        "tracking_number": order.tracking_number,
        "dropoff_location": order.dropoff_location,
    }



@router.get("/stats/{user_id}")
def get_order_stats(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the number of orders bought and sold
    by the specified user.
    """

    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot view another user's order statistics")

    ordered_count = (
        db.query(Order)
        .filter(Order.user_id == user_id)
        .count()
    )

    sold_count = (
        db.query(Order)
        .join(
            Dress,
            Order.dress_id == Dress.id
        )
        .filter(Dress.user_id == user_id)
        .count()
    )

    return {
        "ordered": ordered_count,
        "sold": sold_count,
    }



@router.get("/{user_id}/{order_type}/{status}")
def get_orders(
    user_id: int,
    order_type: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns orders for a user.

    order_type:
        ordered = dresses purchased by the user
        sold    = dresses sold by the user

    status:
        in-progress
        completed
    """

    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot view another user's orders")

    if order_type == "ordered":

        orders = (
            db.query(Order)
            .filter(
                Order.user_id == user_id,
                Order.status == status
            )
            .order_by(Order.created_at.desc())
            .all()
        )

    elif order_type == "sold":

        orders = (
            db.query(Order)
            .join(
                Dress,
                Order.dress_id == Dress.id
            )
            .filter(
                Dress.user_id == user_id,
                Order.status == status
            )
            .order_by(Order.created_at.desc())
            .all()
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid order type")

    result = []

    for order in orders:

        dress = (
            db.query(Dress)
            .filter(Dress.id == order.dress_id)
            .first()
        )

        if not dress:
            continue

        displayed_price = (
            float(order.order_price)
            if order.order_price is not None
            else float(dress.price)
        )

        result.append({
            "id": order.id,

            "status": order.status,

            "order_price": displayed_price,

            "payment_method": order.payment_method,

            "created_at": order.created_at,

            # Delivery information
            "delivery_company": order.delivery_company,

            "delivery_status": (
                order.delivery_status
                or "Awaiting Drop-off"
            ),

            "tracking_number": order.tracking_number,

            "dropoff_location": order.dropoff_location,

            # Dress information
            "dress": {
                "id": dress.id,
                "brand": dress.brand,
                "size": dress.size,
                "price": displayed_price,
                "image_url": dress.image_url,
                "is_sold": dress.is_sold,
            },
        })

    return result



@router.put("/{order_id}/delivery-status")
def update_delivery_status(
    order_id: int,
    status: str,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates the simulated delivery status.

    Only the seller who owns the listed dress can
    update the delivery status.
    """

    # Validate delivery status
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Invalid user")

    if status not in DELIVERY_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Invalid delivery status. Allowed statuses: " + ", ".join(DELIVERY_STATUSES),
        )

    # Find order
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Find dress
    dress = (
        db.query(Dress)
        .filter(Dress.id == order.dress_id)
        .first()
    )

    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")

    # Check that the requesting user is the seller
    if dress.user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the seller can update the delivery status")

    # Update delivery status
    order.delivery_status = status

    db.commit()
    db.refresh(order)

    return {
        "message": "Delivery status updated successfully",
        "order_id": order.id,
        "delivery_status": order.delivery_status,
        "tracking_number": order.tracking_number,
        "delivery_company": order.delivery_company,
    }



@router.put("/{order_id}/complete")
def complete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marks an order as completed.
    """

    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    dress = db.query(Dress).filter(Dress.id == order.dress_id).first()
    if not dress:
        raise HTTPException(status_code=404, detail="Dress not found")
    if current_user.id not in (order.user_id, dress.user_id):
        raise HTTPException(status_code=403, detail="Only the buyer or seller can complete this order")
    if order.status == "completed":
        raise HTTPException(status_code=409, detail="Order is already completed")

    order.status = "completed"

    db.commit()
    db.refresh(order)

    return {
        "message": "Order marked as completed",
        "order_id": order.id,
        "status": order.status,
    }