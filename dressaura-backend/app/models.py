from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DECIMAL,
    ForeignKey,
    TIMESTAMP,
    Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Dress(Base):
    __tablename__ = "dresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    brand = Column(String(100), nullable=False)
    size = Column(String(10), nullable=False)
    condition_status = Column(String(50), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    description = Column(Text)

    # Kept for compatibility with existing listings
    image_url = Column(String(255))

    is_sold = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # New multiple-image relationship
    images = relationship(
        "DressImage",
        back_populates="dress",
        cascade="all, delete-orphan",
        order_by="DressImage.display_order"
    )


class DressImage(Base):
    __tablename__ = "dress_images"

    id = Column(Integer, primary_key=True, index=True)

    dress_id = Column(
        Integer,
        ForeignKey("dresses.id"),
        nullable=False
    )

    image_url = Column(String(255), nullable=False)

    display_order = Column(
        Integer,
        nullable=False,
        default=0
    )

    dress = relationship(
        "Dress",
        back_populates="images"
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    dress_id = Column(Integer, ForeignKey("dresses.id"), nullable=False)

    order_price = Column(DECIMAL(10, 2), nullable=True)

    payment_method = Column(String(50))
    status = Column(String(50), default="pending")

    delivery_company = Column(String(50), nullable=True)

    delivery_status = Column(
        String(50),
        default="Awaiting Drop-off"
    )

    tracking_number = Column(String(50), nullable=True)
    dropoff_location = Column(String(255), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())