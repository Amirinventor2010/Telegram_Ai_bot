import time
from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from config.database import get_session
from db import repository as repo


async def ensure_user(update: Update) -> None:
    """هر آپدیت: کاربر رو در DB ثبت/آپدیت کن."""
    u = update.effective_user
    if not u:
        return

    async with get_session() as session:
        user = await repo.upsert_user(session, u.id, u.username)
        await repo.ensure_daily_reset(session, user)
        await session.commit()


async def is_banned(update: Update) -> bool:
    u = update.effective_user
    if not u:
        return False

    async with get_session() as session:
        user = await repo.get_user_by_tg(session, u.id)
        return bool(user and user.is_banned)


async def check_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """ضد اسپم ساده داخل RAM (برای شروع)."""
    now = time.time()
    last = context.user_data.get("last_action_ts", 0.0)

    if now - last < settings.COOLDOWN_SECONDS:
        await update.effective_message.reply_text("⏳ یه کم آروم‌تر… چند ثانیه دیگه دوباره بزن.")
        return False

    context.user_data["last_action_ts"] = now
    return True


async def check_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Force Join با تنظیم env."""
    if not settings.FORCE_JOIN_ENABLED or not settings.FORCE_JOIN_CHAT:
        return True

    u = update.effective_user
    if not u:
        return False

    try:
        member = await context.bot.get_chat_member(settings.FORCE_JOIN_CHAT, u.id)
        if member.status in ("member", "administrator", "creator"):
            return True
    except Exception:
        # اگر دسترسی/آیدی اشتباه بود، فعلاً بلاک نکنیم.
        return True

    join_link = f"https://t.me/{settings.FORCE_JOIN_CHAT.lstrip('@')}"
    await update.effective_message.reply_text(
        "🔒 برای استفاده از این بخش، اول باید عضو کانال/گروه بشی:\n"
        f"{join_link}\n\n"
        "بعد از عضویت دوباره امتحان کن."
    )
    return False


async def check_daily_quota(update: Update) -> bool:
    """سهمیه روزانه: VIP نامحدود، رایگان روزی FREE_DAILY_EDITS."""
    u = update.effective_user
    if not u:
        return False

    async with get_session() as session:
        user = await repo.get_user_by_tg(session, u.id)
        if not user:
            return False

        await repo.ensure_daily_reset(session, user)

        if user.is_vip:
            await session.commit()
            return True

        if user.daily_used < settings.FREE_DAILY_EDITS:
            await session.commit()
            return True

        await session.commit()

    await update.effective_message.reply_text("🚫 سهمیه امروزت تموم شده. فردا دوباره داری.")
    return False


async def consume_edit(update: Update) -> None:
    """بعد از ثبت درخواست ادیت، یک واحد از سهمیه کم کن (فعلاً فقط رایگان)."""
    u = update.effective_user
    if not u:
        return

    async with get_session() as session:
        user = await repo.get_user_by_tg(session, u.id)
        if not user:
            return

        await repo.ensure_daily_reset(session, user)

        if not user.is_vip:
            user.daily_used += 1

        await session.commit()
