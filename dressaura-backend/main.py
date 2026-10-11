
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.routers import dresses, auth, orders
from app.chat_api import router as chat_router

app = FastAPI(title="Dressaura API")

# CORS: allow the deployed frontend and local development

# CORS: allow the deployed frontend and local development
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


UPLOADS_DIR = Path(__file__).resolve().parent / "app" / "uploads"
os.makedirs(UPLOADS_DIR / "dresses", exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

Base.metadata.create_all(bind=engine)

app.include_router(dresses.router)
app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {"message": "Dressaura backend running"}
