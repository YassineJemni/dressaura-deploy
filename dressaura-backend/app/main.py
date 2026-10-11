import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.chat_api import router as chat_router
from app.database import Base, engine
from app.routers import auth, dresses, orders

app = FastAPI(title="Dressaura API")

# CORS: comma-separated CORS_ORIGINS env var overrides the defaults.
# Optionally set CORS_ORIGIN_REGEX (e.g. r"https://dressaura-deploy.*\.vercel\.app")
# to allow Vercel preview deployments.
DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://dressaura-deploy.vercel.app",
]
origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", ",".join(DEFAULT_ORIGINS)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads folder (ephemeral on Render unless a persistent disk is mounted here)
UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
os.makedirs(UPLOADS_DIR / "dresses", exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Database tables
Base.metadata.create_all(bind=engine)

# Routers
app.include_router(dresses.router)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {"message": "Dressaura backend running"}


@app.get("/health")
def health():
    return {"status": "ok"}
