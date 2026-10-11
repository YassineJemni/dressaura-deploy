from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.routers import dresses, auth, orders
from .chat_api import router as chat_router
import os

app = FastAPI(title="Dressaura API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://dressaura-frontend.vercel.app",
    ],
    allow_origin_regex=r"https://dressaura-frontend-[a-zA-Z0-9-]+-hiam-hasheems-projects\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads folder
os.makedirs("app/uploads/dresses", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

# Database tables
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(dresses.router)
app.include_router(chat_router)
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(orders.router)


# Root
@app.get("/")
def root():
    return {"message": "Dressaura backend running"}
