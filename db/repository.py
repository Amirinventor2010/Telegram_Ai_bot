import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User, Setting, Template, Request

def _day_key() -> int:
    return int(time.time() // 86400)

# -------- Users --------
async def get_user_by_tg(session: AsyncSession, tg_id: int) -> User | None:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    return res.scalar_one_or_none()

async def upsert_user(session: AsyncSession, tg_id: int, username: str | None):
    user = await get_user_by_tg(session, tg_id)
    if user:
        user.username = username
        return user
    user = User(tg_id=tg_id, username=username, daily_reset_day=_day_key())
    session.add(user)
    return user

async def ensure_daily_reset(session: AsyncSession, user: User):
    day = _day_key()
    if user.daily_reset_day != day:
        user.daily_used = 0
        user.daily_reset_day = day

# -------- Settings --------
async def set_setting(session: AsyncSession, key: str, value: str):
    row = await session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))

async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    row = await session.get(Setting, key)
    return row.value if row else default

# -------- Templates --------
async def list_active_templates(session: AsyncSession, for_vip: bool):
    q = select(Template).where(Template.is_active == True)
    if not for_vip:
        q = q.where(Template.vip_only == False)
    res = await session.execute(q.order_by(Template.id.asc()))
    return list(res.scalars().all())

async def list_all_templates(session: AsyncSession):
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
    vip_only: bool = False
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
async def create_request(session: AsyncSession, user_tg_id: int, model: str, images_count: int, prompt: str) -> Request:
    req = Request(
        user_tg_id=user_tg_id,
        model=model,
        images_count=images_count,
        prompt=prompt,
        status="queued",
    )
    session.add(req)
    return req
