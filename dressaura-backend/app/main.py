from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.routers import dresses, auth, orders
from .chat_api import router as chat_router
import os
from pathlib import Path

app = FastAPI(title="Dressaura API")

# CORS

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://dressaura-deploy.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Uploads folder
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
os.makedirs(UPLOADS_DIR / "dresses", exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Database tables
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(dresses.router)
app.include_router(chat_router)
app.include_router(auth.router)
app.include_router(orders.router)


# Root
@app.get("/")
def root():
    return {"message": "Dressaura backend running"}
