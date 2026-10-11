```python
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.routers import dresses, auth

app = FastAPI(title="Dressaura API")

# CORS: allow the deployed frontend and local development
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

os.makedirs("app/uploads/dresses", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

Base.metadata.create_all(bind=engine)

app.include_router(dresses.router)
app.include_router(auth.router)


@app.get("/")
def root():
    return {"message": "Dressaura backend running"}
```
