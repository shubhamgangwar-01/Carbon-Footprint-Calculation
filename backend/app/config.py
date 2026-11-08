"""Runtime configuration from environment variables (see .env.example).
No secrets are hard-coded; development defaults are clearly marked."""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


class Settings:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost:5432/conference_carbon")
        self.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)  # ephemeral if unset (dev only)
        self.admin_email = os.getenv("ADMIN_EMAIL")
        self.admin_password = os.getenv("ADMIN_PASSWORD")
        self.cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
        self.enable_online_geocoding = os.getenv("ENABLE_ONLINE_GEOCODING", "false").lower() == "true"
        self.geocoder_user_agent = os.getenv("GEOCODER_USER_AGENT", "ConferenceCarbonCalculator/1.0")
        self.osrm_url = os.getenv("OSRM_URL", "https://router.project-osrm.org")
        self.nominatim_url = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
        self.factors_json = Path(os.getenv("FACTORS_JSON", str(ROOT / "data" / "processed" / "emission_factors.json")))
        self.reports_dir = Path(os.getenv("REPORTS_DIR", str(ROOT / "backend" / "generated_reports")))
        self.token_ttl_hours = int(os.getenv("TOKEN_TTL_HOURS", "720"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
