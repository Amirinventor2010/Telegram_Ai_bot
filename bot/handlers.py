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


def _is_admin(uid: int) -> bool:
    return uid in settings.ADMIN_IDS


# -------------------------
# /start + Home
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)

    if await is_banned(update):
        await update.message.reply_text("⛔️ دسترسی شما مسدود شده.")
        return States.HOME

    await update.message.reply_text("سلام! از منو یکی رو انتخاب کن.", reply_markup=HOME_KB)
    return States.HOME


async def home_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ensure_user(update)

    if await is_banned(update):
        await update.message.reply_text("⛔️ دسترسی شما مسدود شده.")
        return States.HOME

    if not await check_cooldown(update, context):
        return States.HOME

    text = (update.message.text or "").strip()

    if text == "👤 حساب کاربری":
        await update.message.reply_text("فعلاً حساب کاربری رو مرحله بعد قشنگ می‌کنیم.", reply_markup=HOME_KB)
        return States.HOME

    if text == "ℹ️ درباره ما":
        await update.message.reply_text("این بات برای ویرایش تصویر با هوش مصنوعی ساخته شده.", reply_markup=HOME_KB)
        return States.HOME

    if text == "🎨 تمپلیت‌ها":
        return await show_templates(update, context)

    if text == "🧠 ویرایش تصویر":
        # Gate checks
        if not await check_force_join(update, context):
            return States.HOME
        if not await check_daily_quota(update):
            return States.HOME

        # init flow buffers
        context.user_data["edit_images"] = []
        context.user_data["edit_prompt"] = ""

        await update.message.reply_text(
            "📸 عکس(ها) رو بفرست. می‌تونی چندتا عکس پشت سر هم ارسال کنی.\n"
            "وقتی تموم شد روی ✅ تایید عکس‌ها بزن.",
            reply_markup=edit_images_kb(),
        )
        return States.EDIT_WAIT_IMAGES

    await update.message.reply_text("یکی از دکمه‌های منو رو بزن.", reply_markup=HOME_KB)
    return States.HOME


# -------------------------
# User: Templates
# -------------------------
async def show_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
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
# Admin: /admin
# -------------------------
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not _is_admin(update.effective_user.id):
        await update.message.reply_text("ادمین نیستی.")
        return
    await update.message.reply_text("پنل ادمین:", reply_markup=admin_kb())


# -------------------------
# Edit flow: receive images
# -------------------------
async def edit_receive_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("فقط عکس بفرست لطفاً.", reply_markup=edit_images_kb())
        return States.EDIT_WAIT_IMAGES

    imgs = context.user_data.get("edit_images", [])
    imgs.append(file_id)
    context.user_data["edit_images"] = imgs

    await update.message.reply_text(
        f"✅ عکس دریافت شد. تعداد عکس‌ها: {len(imgs)}\n"
        "اگر عکس دیگه‌ای داری بفرست. اگر نه، ✅ تایید عکس‌ها رو بزن.",
        reply_markup=edit_images_kb(),
    )
    return States.EDIT_WAIT_IMAGES


# -------------------------
# Edit flow: receive prompt
# -------------------------
async def edit_receive_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (update.message.text or "").strip()
    if not prompt:
        await update.message.reply_text("پرامپت خالیه. دوباره بفرست.", reply_markup=edit_prompt_kb())
        return States.EDIT_WAIT_PROMPT

    # اگر کاربر "ok" نوشت و تمپلیت انتخاب شده داشت، یعنی فقط همون تمپلیت
    if prompt.lower() == "ok" and context.user_data.get("selected_template_id"):
        prompt = "OK"

    context.user_data["edit_prompt"] = prompt

    await update.message.reply_text(
        f"🧾 پرامپت ثبت شد:\n{prompt}\n\nحالا 🚀 شروع پردازش رو بزن.",
        reply_markup=edit_final_confirm_kb(),
    )
    return States.EDIT_CONFIRM


# -------------------------
# Callback router
# -------------------------
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    # =========================
    # EDIT FLOW callbacks
    # =========================
    if data == "edit:cancel":
        context.user_data.pop("edit_images", None)
        context.user_data.pop("edit_prompt", None)
        await q.message.reply_text("لغو شد. برگشتیم منو.", reply_markup=HOME_KB)
        return States.HOME

    if data == "edit:images:clear":
        context.user_data["edit_images"] = []
        await q.message.reply_text("🗑 عکس‌ها پاک شد. دوباره عکس بفرست.", reply_markup=edit_images_kb())
        return States.EDIT_WAIT_IMAGES

    if data == "edit:images:confirm":
        imgs = context.user_data.get("edit_images", [])
        if not imgs:
            await q.message.reply_text("هنوز عکسی نفرستادی. اول عکس بفرست.", reply_markup=edit_images_kb())
            return States.EDIT_WAIT_IMAGES

        selected_tpl = context.user_data.get("selected_template_id")
        if selected_tpl:
            await q.message.reply_text(
                "✍️ پرامپت رو بفرست.\n"
                "اگر می‌خوای فقط از تمپلیت استفاده کنی، بنویس: ok",
                reply_markup=edit_prompt_kb(),
            )
        else:
            await q.message.reply_text(
                "✍️ پرامپت رو بفرست.\n"
                "اگر دوست داری از تمپلیت استفاده کنی، اول از بخش 🎨 تمپلیت‌ها یکی انتخاب کن.",
                reply_markup=edit_prompt_kb(),
            )
        return States.EDIT_WAIT_PROMPT

    if data == "edit:prompt:confirm":
        await q.message.reply_text("پرامپت رو به صورت متن ارسال کن.")
        return States.EDIT_WAIT_PROMPT

    if data == "edit:go":
        imgs = context.user_data.get("edit_images", [])
        user_prompt = (context.user_data.get("edit_prompt") or "").strip()

        if not imgs:
            await q.message.reply_text("عکس‌ها خالیه. دوباره شروع کن.", reply_markup=HOME_KB)
            return States.HOME

        template_id = context.user_data.get("selected_template_id")
        final_prompt = user_prompt

        if template_id:
            async with get_session() as session:
                tpl = await repo.get_template(session, int(template_id))
            if tpl:
                if user_prompt.upper() == "OK":
                    final_prompt = tpl.prompt
                else:
                    final_prompt = f"{tpl.prompt}\n\nUser instructions:\n{user_prompt}"

        if not final_prompt.strip():
            await q.message.reply_text("پرامپت ثبت نشده. دوباره بفرست.", reply_markup=HOME_KB)
            return States.HOME

        # ثبت درخواست
        u = update.effective_user
        async with get_session() as session:
            await repo.create_request(
                session,
                user_tg_id=u.id,
                model=settings.GEMINI_MODEL,
                images_count=len(imgs),
                prompt=final_prompt,
            )
            await session.commit()

        await consume_edit(update)

        context.user_data.pop("edit_images", None)
        context.user_data.pop("edit_prompt", None)

        await q.message.reply_text(
            "✅ درخواست ثبت شد و رفت تو صف پردازش.\n"
            "مرحله بعد: صف و Worker واقعی + خروجی تصویر.",
            reply_markup=HOME_KB,
        )
        return States.HOME

    # =========================
    # USER template callbacks
    # =========================
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

    # =========================
    # ADMIN callbacks
    # =========================
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
                await q.message.reply_photo(photo=tpl.sample_file_id, caption=text, reply_markup=admin_template_actions_kb(tpl.id, tpl.is_active))
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
    title = (update.message.text or "").strip()
    if not title:
        await update.message.reply_text("اسم خالیه. دوباره بفرست.")
        return States.ADM_TPL_TITLE

    async with get_session() as session:
        exists = await repo.title_exists(session, title)
    if exists:
        await update.message.reply_text("این اسم قبلاً استفاده شده. یه اسم دیگه بده:")
        return States.ADM_TPL_TITLE

    context.user_data["adm_new_tpl"]["title"] = title
    await update.message.reply_text("توضیح تمپلیت رو بفرست:")
    return States.ADM_TPL_DESC


async def adm_tpl_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = (update.message.text or "").strip()
    if not desc:
        await update.message.reply_text("توضیح خالیه. دوباره بفرست.")
        return States.ADM_TPL_DESC

    context.user_data["adm_new_tpl"]["description"] = desc
    await update.message.reply_text("Prompt پایه رو بفرست:")
    return States.ADM_TPL_PROMPT


async def adm_tpl_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = (update.message.text or "").strip()
    if not prompt:
        await update.message.reply_text("Prompt خالیه. دوباره بفرست.")
        return States.ADM_TPL_PROMPT

    context.user_data["adm_new_tpl"]["prompt"] = prompt
    await update.message.reply_text("حالا یک عکس نمونه بفرست (یا بنویس: skip)")
    return States.ADM_TPL_SAMPLE


async def adm_tpl_sample(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sample_file_id = None

    if update.message.text and update.message.text.strip().lower() == "skip":
        sample_file_id = None
    elif update.message.photo:
        sample_file_id = update.message.photo[-1].file_id
    elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        sample_file_id = update.message.document.file_id
    else:
        await update.message.reply_text("یا عکس بفرست یا بنویس: skip")
        return States.ADM_TPL_SAMPLE

    data = context.user_data.get("adm_new_tpl", {})
    title = data.get("title")
    description = data.get("description")
    prompt = data.get("prompt")

    async with get_session() as session:
        await repo.create_template(session, title=title, description=description, prompt=prompt, sample_file_id=sample_file_id)
        await session.commit()

    context.user_data.pop("adm_new_tpl", None)
    await update.message.reply_text("✅ تمپلیت اضافه شد.", reply_markup=HOME_KB)
    return States.HOME
