from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Setting, Template, Request


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_key_utc() -> int:
    """
    کلید روز پایدار بر اساس UTC: YYYYMMDD
    (بهتر از time()//86400 چون با timezone و DST و اینا قاطی نمی‌کنه)
    """
    d = _utc_now().date()
    return d.year * 10000 + d.month * 100 + d.day


# -------- Users --------
async def get_user_by_tg(session: AsyncSession, tg_id: int) -> User | None:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    return res.scalar_one_or_none()


async def upsert_user(session: AsyncSession, tg_id: int, username: str | None) -> User:
    """
    ایجاد/آپدیت کاربر.
    نکته: first_seen و last_seen باید datetime باشند، نه int epoch.
    """
    user = await get_user_by_tg(session, tg_id)
    now = _utc_now()

    if user:
        user.username = username
        user.last_seen = now
        return user

    user = User(
        tg_id=tg_id,
        username=username,
        daily_reset_day=_day_key_utc(),
        daily_used=0,
        credits=0,
        first_seen=now,
        last_seen=now,
    )
    session.add(user)
    return user


async def ensure_daily_reset(session: AsyncSession, user: User) -> None:
    """
    اگر روز عوض شده، سهمیه روزانه ریست می‌شود.
    """
    day = _day_key_utc()
    if user.daily_reset_day != day:
        user.daily_used = 0
        user.daily_reset_day = day


# -------- Settings --------
async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))


async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    row = await session.get(Setting, key)
    return row.value if row else default


# -------- Templates --------
async def list_active_templates(session: AsyncSession, for_vip: bool) -> list[Template]:
    q = select(Template).where(Template.is_active.is_(True))
    if not for_vip:
        q = q.where(Template.vip_only.is_(False))
    res = await session.execute(q.order_by(Template.id.asc()))
    return list(res.scalars().all())


async def list_all_templates(session: AsyncSession) -> list[Template]:
    res = await session.execute(select(Template).order_by(Template.id.asc()))
    return list(res.scalars().all())


async def get_template(session: AsyncSession, template_id: int) -> Template | None:
    res = await session.execute(select(Template).where(Template.id == template_id))
    return res.scalar_one_or_none()


async def title_exists(session: AsyncSession, title: str) -> bool:
    res = await session.execute(select(Template.id).where(Template.title == title))
    return res.scalar_one_or_none() is not None


async def create_template(
    session: AsyncSession,
    title: str,
    description: str,
    prompt: str,
    sample_file_id: str | None,
    vip_only: bool = False,
) -> Template:
    tpl = Template(
        title=title,
        description=description,
        prompt=prompt,
        sample_file_id=sample_file_id,
        vip_only=vip_only,
        is_active=True,
    )
    session.add(tpl)
    return tpl


async def toggle_template_active(session: AsyncSession, template_id: int) -> bool:
    tpl = await get_template(session, template_id)
    if not tpl:
        return False
    tpl.is_active = not tpl.is_active
    return True


async def delete_template(session: AsyncSession, template_id: int) -> bool:
    tpl = await get_template(session, template_id)
    if not tpl:
        return False
    await session.delete(tpl)
    return True


# -------- Requests --------
async def create_request(
    session: AsyncSession,
    user_tg_id: int,
    model: str,
    images_count: int,
    prompt: str,
) -> Request:
    req = Request(
        user_tg_id=user_tg_id,
        model=model,
        images_count=images_count,
        prompt=prompt,
        status="queued",
    )
    session.add(req)
    return req


async def count_requests_for_user(session: AsyncSession, user_tg_id: int) -> int:
    res = await session.execute(select(func.count(Request.id)).where(Request.user_tg_id == user_tg_id))
    return int(res.scalar() or 0)


async def list_recent_requests_for_user(
    session: AsyncSession,
    user_tg_id: int,
    limit: int = 5,
) -> list[Request]:
    res = await session.execute(
        select(Request)
        .where(Request.user_tg_id == user_tg_id)
        .order_by(desc(Request.id))
        .limit(limit)
    )
    return list(res.scalars().all())
