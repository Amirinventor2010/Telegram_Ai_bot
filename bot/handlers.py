from __future__ import annotations

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import settings
from config.database import get_session
from bot.states import States
from bot.keyboards import (
    HOME_KB,
    templates_inline_kb,
    template_preview_kb,
    admin_kb,
    admin_templates_manage_kb,
    admin_template_actions_kb,
    edit_images_kb,
    edit_prompt_kb,
    edit_final_confirm_kb,
    account_kb,
)
from bot.middlewares import (
    ensure_user,
    is_banned,
    check_cooldown,
    check_force_join,
    check_daily_quota,
    consume_edit,
)
from db import repository as repo
from services.queue import enqueue_request


def _is_admin(uid: int) -> bool:
    return uid in settings.ADMIN_IDS


def _ts_to_date(ts: int | None) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _get_photo_file_id(update: Update) -> str | None:
    msg = update.effective_message
    if not msg:
        return None

    if getattr(msg, "photo", None):
        return msg.photo[-1].file_id

    doc = getattr(msg, "document", None)
    if doc and (doc.mime_type or "").startswith("image/"):
        return doc.file_id

    return None


# -------------------------
# /start + Home
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)

    if await is_banned(update):
        await update.effective_message.reply_text("⛔️ دسترسی شما مسدود شده.")
        return States.HOME

    await update.effective_message.reply_text("سلام! از منو یکی رو انتخاب کن.", reply_markup=HOME_KB)
    return States.HOME


async def home_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)

    if await is_banned(update):
        await update.effective_message.reply_text("⛔️ دسترسی شما مسدود شده.")
        return States.HOME

    if not await check_cooldown(update, context):
        return States.HOME

    text = (update.effective_message.text or "").strip()

    if text == "👤 حساب کاربری":
        return await show_account(update, context)

    if text == "ℹ️ درباره ما":
        await update.effective_message.reply_text("این بات برای ویرایش تصویر با هوش مصنوعی ساخته شده.", reply_markup=HOME_KB)
        return States.HOME

    if text == "🎨 تمپلیت‌ها":
        return await show_templates(update, context)

    if text == "🧠 ویرایش تصویر":
        return await edit_start(update, context)

    await update.effective_message.reply_text("یکی از دکمه‌های منو رو بزن.", reply_markup=HOME_KB)
    return States.HOME


# -------------------------
# User: Account
# -------------------------
async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u:
        return States.HOME

    async with get_session() as session:
        user = await repo.get_user_by_tg(session, u.id)
        if not user:
            await update.effective_message.reply_text("یه مشکلی پیش اومد. دوباره /start بزن.", reply_markup=HOME_KB)
            return States.HOME

        await repo.ensure_daily_reset(session, user)
        total_reqs = await repo.count_requests_for_user(session, u.id)
        await session.commit()

        is_vip = bool(user.is_vip)
        used = int(user.daily_used or 0)
        free = int(settings.FREE_DAILY_EDITS)
        remaining = "نامحدود" if is_vip else max(0, free - used)

        lang = (user.lang or "fa").lower()

    text = (
        f"👤 حساب کاربری\n\n"
        f"🆔 ID: {u.id}\n"
        f"🔖 Username: @{u.username if u.username else '-'}\n"
        f"💎 VIP: {'✅ فعال' if is_vip else '❌ غیرفعال'}\n"
        f"📆 سهمیه امروز: {used}/{free} | باقی‌مانده: {remaining}\n"
        f"📦 تعداد کل درخواست‌ها: {total_reqs}\n"
        f"🌐 زبان: {lang}\n"
        f"🕒 اولین ورود: {_ts_to_date(getattr(user, 'first_seen', None))}\n"
        f"🕒 آخرین فعالیت: {_ts_to_date(getattr(user, 'last_seen', None))}\n"
    )

    await update.effective_message.reply_text(text, reply_markup=account_kb(lang))
    return States.HOME


# -------------------------
# User: Templates
# -------------------------
async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u:
        return States.HOME

    async with get_session() as session:
        user = await repo.get_user_by_tg(session, u.id)
        is_vip = bool(user and user.is_vip)
        tpls = await repo.list_active_templates(session, for_vip=is_vip)

    if not tpls:
        await update.effective_message.reply_text("فعلاً هیچ تمپلیتی نداریم. ادمین باید اضافه کنه.", reply_markup=HOME_KB)
        return States.HOME

    items = [(t.id, t.title) for t in tpls]
    await update.effective_message.reply_text("یکی از تمپلیت‌ها رو انتخاب کن:", reply_markup=templates_inline_kb(items))
    return States.HOME


# -------------------------
# User: Edit Flow
# -------------------------
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_force_join(update, context):
        return States.HOME

    if not await check_daily_quota(update):
        return States.HOME

    context.user_data["edit_images"] = []
    context.user_data["edit_prompt"] = None

    max_images = settings.MAX_IMAGES
    await update.effective_message.reply_text(
        f"📸 عکس(ها) رو بفرست (می‌تونی چندتا بفرستی، حداکثر {max_images} تا).\n"
        f"بعدش روی «✅ تایید عکس‌ها» بزن.",
        reply_markup=edit_images_kb(),
    )
    return States.EDIT_WAIT_IMAGES


async def edit_wait_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)

    if await is_banned(update):
        await update.effective_message.reply_text("⛔️ دسترسی شما مسدود شده.")
        return States.HOME

    if not await check_cooldown(update, context):
        return States.EDIT_WAIT_IMAGES

    file_id = _get_photo_file_id(update)
    if not file_id:
        await update.effective_message.reply_text("فقط عکس بفرست (photo یا document تصویر).", reply_markup=edit_images_kb())
        return States.EDIT_WAIT_IMAGES

    images: list[str] = context.user_data.get("edit_images", [])
    if len(images) >= settings.MAX_IMAGES:
        await update.effective_message.reply_text(
            f"🚫 بیشتر از {settings.MAX_IMAGES} تا نمی‌شه.\n"
            "روی «✅ تایید عکس‌ها» بزن یا «🗑 پاک کردن عکس‌ها».",
            reply_markup=edit_images_kb(),
        )
        return States.EDIT_WAIT_IMAGES

    images.append(file_id)
    context.user_data["edit_images"] = images

    await update.effective_message.reply_text(
        f"✅ عکس ثبت شد. ({len(images)}/{settings.MAX_IMAGES})\n"
        "می‌تونی عکس دیگه هم بفرستی یا تایید کنی.",
        reply_markup=edit_images_kb(),
    )
    return States.EDIT_WAIT_IMAGES


async def edit_wait_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)

    if await is_banned(update):
        await update.effective_message.reply_text("⛔️ دسترسی شما مسدود شده.")
        return States.HOME

    if not await check_cooldown(update, context):
        return States.EDIT_WAIT_PROMPT

    prompt = (update.effective_message.text or "").strip()
    if not prompt:
        await update.effective_message.reply_text("پرامپت خالیه. دوباره بفرست:", reply_markup=edit_prompt_kb())
        return States.EDIT_WAIT_PROMPT

    context.user_data["edit_prompt"] = prompt

    await update.effective_message.reply_text(
        "✅ پرامپت ثبت شد.\nحالا تایید نهایی:",
        reply_markup=edit_final_confirm_kb(),
    )
    return States.EDIT_CONFIRM


# -------------------------
# Admin: /admin
# -------------------------
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not _is_admin(update.effective_user.id):
        await update.effective_message.reply_text("ادمین نیستی.")
        return
    await update.effective_message.reply_text("پنل ادمین:", reply_markup=admin_kb())


# -------------------------
# Callback router
# -------------------------
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return States.HOME

    await q.answer()
    data = q.data or ""

    # ---- ACCOUNT callbacks ----
    if data == "acc:back":
        await q.message.reply_text("برگشتیم منو.", reply_markup=HOME_KB)
        return States.HOME

    if data == "acc:history":
        u = update.effective_user
        if not u:
            return States.HOME

        async with get_session() as session:
            rows = await repo.list_recent_requests_for_user(session, u.id, limit=5)

        if not rows:
            await q.message.reply_text("فعلاً هیچ درخواستی ثبت نکردی.", reply_markup=HOME_KB)
            return States.HOME

        lines = []
        for r in rows:
            lines.append(f"#{r.id} | {r.status} | {r.images_count} عکس | مدل: {r.model}")

        await q.message.reply_text("🧾 5 درخواست آخر:\n" + "\n".join(lines), reply_markup=HOME_KB)
        return States.HOME

    if data == "acc:lang:toggle":
        u = update.effective_user
        if not u:
            return States.HOME

        async with get_session() as session:
            user = await repo.get_user_by_tg(session, u.id)
            if not user:
                await q.message.reply_text("مشکل کاربر. دوباره /start بزن.")
                return States.HOME
            cur = (user.lang or "fa").lower()
            user.lang = "en" if cur == "fa" else "fa"
            await session.commit()
            new_lang = user.lang

        await q.message.reply_text(f"✅ زبان تغییر کرد: {new_lang}", reply_markup=HOME_KB)
        return States.HOME

    # ---- USER template callbacks ----
    if data == "tpl:back":
        await q.message.reply_text("برگشتیم منو.", reply_markup=HOME_KB)
        return States.HOME

    if data == "tpl:list":
        fake_update = Update(update.update_id, message=q.message)
        fake_update._effective_user = update.effective_user
        return await show_templates(fake_update, context)

    if data.startswith("tpl:view:"):
        template_id = int(data.split(":")[-1])
        async with get_session() as session:
            tpl = await repo.get_template(session, template_id)

        if not tpl:
            await q.message.reply_text("این تمپلیت پیدا نشد.")
            return States.HOME

        caption = (
            f"**{tpl.title}**\n\n"
            f"{tpl.description}\n\n"
            f"🧾 Prompt پایه:\n{tpl.prompt}"
        )

        if tpl.sample_file_id:
            await q.message.reply_photo(
                photo=tpl.sample_file_id,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=template_preview_kb(tpl.id),
            )
        else:
            await q.message.reply_text(caption, parse_mode="Markdown", reply_markup=template_preview_kb(tpl.id))

        return States.HOME

    if data.startswith("tpl:use:"):
        template_id = int(data.split(":")[-1])
        context.user_data["selected_template_id"] = template_id
        await q.message.reply_text("✅ تمپلیت انتخاب شد.", reply_markup=HOME_KB)
        return States.HOME

    # ---- EDIT callbacks ----
    if data == "edit:cancel":
        context.user_data.pop("edit_images", None)
        context.user_data.pop("edit_prompt", None)
        await q.message.reply_text("لغو شد. برگشتیم منو.", reply_markup=HOME_KB)
        return States.HOME

    if data == "edit:images:clear":
        context.user_data["edit_images"] = []
        await q.message.reply_text("🗑 عکس‌ها پاک شد. دوباره عکس‌ها رو بفرست.", reply_markup=edit_images_kb())
        return States.EDIT_WAIT_IMAGES

    if data == "edit:images:confirm":
        images: list[str] = context.user_data.get("edit_images", [])
        if not images:
            await q.message.reply_text("اول حداقل یک عکس بفرست.", reply_markup=edit_images_kb())
            return States.EDIT_WAIT_IMAGES

        await q.message.reply_text(
            "✍️ حالا پرامپت رو بفرست.\n"
            "مثال: «پوست رو طبیعی‌تر کن، نور نرم‌تر، پس‌زمینه ساده»",
            reply_markup=edit_prompt_kb(),
        )
        return States.EDIT_WAIT_PROMPT

    if data == "edit:go":
        fake_update = Update(update.update_id, message=q.message)
        fake_update._effective_user = update.effective_user

        if not await check_force_join(fake_update, context):
            return States.HOME

        if not await check_daily_quota(fake_update):
            return States.HOME

        u = update.effective_user
        if not u:
            await q.message.reply_text("مشکل کاربر. دوباره /start بزن.")
            return States.HOME

        images: list[str] = context.user_data.get("edit_images", [])
        prompt: str | None = context.user_data.get("edit_prompt")
        if not images or not prompt:
            await q.message.reply_text("اطلاعات ناقصه. دوباره از اول برو.", reply_markup=HOME_KB)
            return States.HOME

        selected_template_id = context.user_data.get("selected_template_id")
        final_prompt = prompt
        if selected_template_id:
            async with get_session() as session:
                tpl = await repo.get_template(session, int(selected_template_id))
            if tpl and tpl.prompt:
                final_prompt = f"{tpl.prompt}\n\nUser prompt: {prompt}"

        async with get_session() as session:
            req = await repo.create_request(
                session,
                user_tg_id=u.id,
                model=settings.GEMINI_MODEL,
                images_count=len(images),
                prompt=final_prompt,
            )
            await session.commit()

        await consume_edit(fake_update)

        await enqueue_request(
            request_id=req.id,
            user_tg_id=u.id,
            chat_id=q.message.chat_id,
            image_file_ids=images,
            prompt=final_prompt,
        )

        context.user_data.pop("edit_images", None)
        context.user_data.pop("edit_prompt", None)

        await q.message.reply_text("🚀 درخواست ثبت شد و رفت تو صف پردازش. نتیجه که آماده بشه می‌فرستم.", reply_markup=HOME_KB)
        return States.HOME

    # ---- ADMIN callbacks (فعلاً همون قبلی‌ها) ----
    if data.startswith("adm:"):
        if not update.effective_user or not _is_admin(update.effective_user.id):
            await q.message.reply_text("ادمین نیستی.")
            return States.HOME

        if data == "adm:back":
            await q.message.reply_text("پنل ادمین:", reply_markup=admin_kb())
            return States.HOME

        if data == "adm:tpl:add":
            context.user_data["adm_new_tpl"] = {}
            await q.message.reply_text("اسم تمپلیت رو بفرست (همون متن دکمه):")
            return States.ADM_TPL_TITLE

        if data == "adm:tpl:list":
            async with get_session() as session:
                all_tpls = await repo.list_all_templates(session)
            if not all_tpls:
                await q.message.reply_text("هیچ تمپلیتی ثبت نشده.")
                return States.HOME

            items = [(t.id, t.title, t.is_active) for t in all_tpls]
            await q.message.reply_text("مدیریت تمپلیت‌ها:", reply_markup=admin_templates_manage_kb(items))
            return States.HOME

        if data.startswith("adm:tpl:view:"):
            template_id = int(data.split(":")[-1])
            async with get_session() as session:
                tpl = await repo.get_template(session, template_id)

            if not tpl:
                await q.message.reply_text("پیدا نشد.")
                return States.HOME

            text = (
                f"📌 {tpl.title}\n"
                f"{'✅ فعال' if tpl.is_active else '❌ غیرفعال'}\n\n"
                f"{tpl.description}\n\n"
                f"Prompt:\n{tpl.prompt}"
            )
            if tpl.sample_file_id:
                await q.message.reply_photo(
                    photo=tpl.sample_file_id,
                    caption=text,
                    reply_markup=admin_template_actions_kb(tpl.id, tpl.is_active),
                )
            else:
                await q.message.reply_text(text, reply_markup=admin_template_actions_kb(tpl.id, tpl.is_active))
            return States.HOME

        if data.startswith("adm:tpl:toggle:"):
            template_id = int(data.split(":")[-1])
            async with get_session() as session:
                ok = await repo.toggle_template_active(session, template_id)
                await session.commit()
            await q.message.reply_text("✅ تغییر کرد." if ok else "❌ پیدا نشد.")
            return States.HOME

        if data.startswith("adm:tpl:del:"):
            template_id = int(data.split(":")[-1])
            async with get_session() as session:
                ok = await repo.delete_template(session, template_id)
                await session.commit()
            await q.message.reply_text("✅ حذف شد." if ok else "❌ پیدا نشد.")
            return States.HOME

    return States.HOME


# -------------------------
# Admin Wizard Steps
# -------------------------
async def adm_tpl_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = (update.effective_message.text or "").strip()
    if not title:
        await update.effective_message.reply_text("اسم خالیه. دوباره بفرست.")
        return States.ADM_TPL_TITLE

    async with get_session() as session:
        exists = await repo.title_exists(session, title)
    if exists:
        await update.effective_message.reply_text("این اسم قبلاً استفاده شده. یه اسم دیگه بده:")
        return States.ADM_TPL_TITLE

    context.user_data["adm_new_tpl"]["title"] = title
    await update.effective_message.reply_text("توضیح تمپلیت رو بفرست:")
    return States.ADM_TPL_DESC


async def adm_tpl_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = (update.effective_message.text or "").strip()
    if not desc:
        await update.effective_message.reply_text("توضیح خالیه. دوباره بفرست.")
        return States.ADM_TPL_DESC

    context.user_data["adm_new_tpl"]["description"] = desc
    await update.effective_message.reply_text("Prompt پایه رو بفرست:")
    return States.ADM_TPL_PROMPT


async def adm_tpl_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (update.effective_message.text or "").strip()
    if not prompt:
        await update.effective_message.reply_text("Prompt خالیه. دوباره بفرست.")
        return States.ADM_TPL_PROMPT

    context.user_data["adm_new_tpl"]["prompt"] = prompt
    await update.effective_message.reply_text("حالا یک عکس نمونه بفرست (یا بنویس: skip)")
    return States.ADM_TPL_SAMPLE


async def adm_tpl_sample(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sample_file_id = None

    if update.effective_message.text and update.effective_message.text.strip().lower() == "skip":
        sample_file_id = None
    elif getattr(update.effective_message, "photo", None):
        sample_file_id = update.effective_message.photo[-1].file_id
    elif getattr(update.effective_message, "document", None) and (update.effective_message.document.mime_type or "").startswith("image/"):
        sample_file_id = update.effective_message.document.file_id
    else:
        await update.effective_message.reply_text("یا عکس بفرست یا بنویس: skip")
        return States.ADM_TPL_SAMPLE

    data = context.user_data.get("adm_new_tpl", {})
    title = data.get("title")
    description = data.get("description")
    prompt = data.get("prompt")

    async with get_session() as session:
        await repo.create_template(
            session,
            title=title,
            description=description,
            prompt=prompt,
            sample_file_id=sample_file_id,
        )
        await session.commit()

    context.user_data.pop("adm_new_tpl", None)
    await update.effective_message.reply_text("✅ تمپلیت اضافه شد.", reply_markup=HOME_KB)
    return States.HOME
