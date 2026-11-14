"""Vercel serverless entrypoint: exposes the FastAPI app (all /api/* routes)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ.setdefault("REPORTS_DIR", "/tmp/reports")   # only /tmp is writable on Vercel
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
os.environ.setdefault("AUTO_MIGRATE", "false")          # migrate/seed once from your laptop instead
os.makedirs("/tmp/reports", exist_ok=True)

from app.main import app  # noqa: E402,F401
