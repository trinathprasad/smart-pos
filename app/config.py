from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "false").lower() == "true"
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'billing.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EXPORT_DIR = BASE_DIR / "exports"
