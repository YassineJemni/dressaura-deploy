# Render entrypoint: `uvicorn main:app --host 0.0.0.0 --port $PORT`
# The application itself lives in app/main.py (single source of truth).
from app.main import app  # noqa: F401
