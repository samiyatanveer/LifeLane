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
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MODEL_DIR = PROJECT_ROOT / os.getenv("MODEL_DIR", "models")
API_VERSION = "2.0.0"
PROJECT_NAME = "LifeLane"
