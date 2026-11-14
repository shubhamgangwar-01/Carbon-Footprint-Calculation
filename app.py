"""Hugging Face Spaces (Gradio SDK) launcher: runs the FastAPI backend on port 7860."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
os.environ.setdefault("REPORTS_DIR", "/tmp/reports")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
os.makedirs("/tmp/reports", exist_ok=True)
os.chdir(BACKEND)           # alembic.ini and migrations are resolved relative to backend/
sys.path.insert(0, BACKEND)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
