"""Configuration read from environment variables."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path=None):
    """Load KEY=VALUE pairs from a .env file without overriding real environment variables."""
    path = Path(path) if path else BASE_DIR / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def _flag(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def build_config():
    env = os.environ.get
    production = env("APP_ENV", "development").strip().lower() == "production"
    return {
        "APP_ENV": "production" if production else "development",
        "SECRET_KEY": env("SECRET_KEY") or None,
        "ADMIN_USERNAME": env("ADMIN_USERNAME", "").strip(),
        "ADMIN_PASSWORD_HASH": env("ADMIN_PASSWORD_HASH", "").strip(),
        "DATA_FILE": env("DATA_FILE", str(BASE_DIR / "data" / "runtime" / "library.json")),
        "SAMPLE_FILE": env("SAMPLE_FILE", str(BASE_DIR / "data" / "sample" / "sample_data.json")),
        "SEED_SAMPLE_DATA": _flag("SEED_SAMPLE_DATA", True),
        "FINE_PER_DAY": env("FINE_PER_DAY", "2.00"),
        "LOAN_DAYS": _int("LOAN_DAYS", 14),
        "MAX_LOANS_PER_MEMBER": _int("MAX_LOANS_PER_MEMBER", 5),
        "CURRENCY_SYMBOL": env("CURRENCY_SYMBOL", "\u20b9"),
        "TIMEZONE": env("TIMEZONE", "Asia/Kolkata"),
        "TRUST_PROXY": _flag("TRUST_PROXY", production),
        "SESSION_COOKIE_SECURE": _flag("SESSION_COOKIE_SECURE", production),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(minutes=_int("SESSION_MINUTES", 30)),
        "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
        "LOGIN_MAX_ATTEMPTS": _int("LOGIN_MAX_ATTEMPTS", 5),
        "LOGIN_LOCK_SECONDS": _int("LOGIN_LOCK_SECONDS", 300),
    }
