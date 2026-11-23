"""Backend configuration — reads from .env and settings.yaml."""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Ensure lifelane_engine is importable
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{PROJECT_ROOT}/lifelane.db")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000").split(",")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MODEL_DIR = PROJECT_ROOT / os.getenv("MODEL_DIR", "models")
API_VERSION = "2.0.0"
PROJECT_NAME = "LifeLane"
AUTH_SECRET = os.getenv("AUTH_SECRET", "change-this-lifelane-demo-secret-before-deployment")
AUTH_TOKEN_TTL_MINUTES = int(os.getenv("AUTH_TOKEN_TTL_MINUTES", "480"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
PASSWORD_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "15"))
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
# In local development, links are written to the backend log when SMTP is absent.
EMAIL_DEV_LOG_LINKS = os.getenv("EMAIL_DEV_LOG_LINKS", "true").lower() == "true"
# Kept for the existing admin-generated staff-link endpoint only.
AUTH_SHOW_RESET_LINKS = os.getenv("AUTH_SHOW_RESET_LINKS", "false").lower() == "true"
# Public OSRM is suitable for development and demonstrations. Deployments should
# point this at a managed or self-hosted routing service instead.
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")
ROUTING_TIMEOUT_SECONDS = float(os.getenv("ROUTING_TIMEOUT_SECONDS", "10"))
SEED_ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME")
SEED_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD")
