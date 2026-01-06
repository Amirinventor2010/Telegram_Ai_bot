import os

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _get_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name, "")).strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in environment")

# Admin IDs
ADMIN_IDS = []
_admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
if _admin_ids_raw:
    for x in _admin_ids_raw.split(","):
        x = x.strip()
        if x.isdigit():
            ADMIN_IDS.append(int(x))

# Force Join
FORCE_JOIN_ENABLED = _get_bool("FORCE_JOIN_ENABLED", False)
FORCE_JOIN_CHAT = os.getenv("FORCE_JOIN_CHAT", "").strip() or None

# Limits
FREE_DAILY_EDITS = _get_int("FREE_DAILY_EDITS", 5)
COOLDOWN_SECONDS = _get_int("COOLDOWN_SECONDS", 20)
MAX_IMAGES = _get_int("MAX_IMAGES", 6)

# AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image").strip()

# Database (اولویت با DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    db_user = os.getenv("DB_USER", "telegram_ai_user")
    db_password = os.getenv("DB_PASSWORD", "StrongPasswordHere")
    db_name = os.getenv("DB_NAME", "telegram_ai_bot")
    db_host = os.getenv("DB_HOST", "localhost")  # داخل Docker باید db باشه
    db_port = os.getenv("DB_PORT", "5432")
    DATABASE_URL = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
