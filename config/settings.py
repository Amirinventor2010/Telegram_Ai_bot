import os

def _parse_int_list(s: str) -> list[int]:
    out = []
    for x in (s or "").split(","):
        x = x.strip()
        if x.isdigit():
            out.append(int(x))
    return out

BOT_TOKEN = os.environ["BOT_TOKEN"]

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "telegram_ai_bot")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

ADMIN_IDS = set(_parse_int_list(os.environ.get("ADMIN_IDS", "")))

FORCE_JOIN_ENABLED = os.environ.get("FORCE_JOIN_ENABLED", "false").lower() == "true"
FORCE_JOIN_CHAT = os.environ.get("FORCE_JOIN_CHAT", "")

FREE_DAILY_EDITS = int(os.environ.get("FREE_DAILY_EDITS", "5"))
COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "20"))
MAX_IMAGES = int(os.environ.get("MAX_IMAGES", "6"))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-image")

def db_url() -> str:
    # asyncpg driver
    return (
        f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
