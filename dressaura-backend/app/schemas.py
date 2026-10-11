from pydantic import BaseModel, EmailStr
from typing import Optional, List




class DressCreate(BaseModel):
    brand: str
    size: str
    condition_status: str
    price: float
    description: Optional[str] = None


class DressImageOut(BaseModel):
    id: int
    dress_id: int
    image_url: str
    display_order: int

    class Config:
        from_attributes = True


class DressOut(BaseModel):
    id: int
    user_id: Optional[int]
    brand: str
    size: str
    condition_status: str
    price: float
    description: Optional[str]
    image_url: Optional[str]
    images: List[DressImageOut] = []

    class Config:
        from_attributes = True


class ImageReorderRequest(BaseModel):
    image_ids: List[int]




class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class ProfileUpdate(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True