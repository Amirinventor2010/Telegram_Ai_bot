from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


HOME_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("👤 حساب کاربری"), KeyboardButton("🎨 تمپلیت‌ها")],
        [KeyboardButton("🧠 ویرایش تصویر"), KeyboardButton("ℹ️ درباره ما")],
    ],
    resize_keyboard=True
)


def templates_inline_kb(items: list[tuple[int, str]]):
    rows = [[InlineKeyboardButton(title, callback_data=f"tpl:view:{tid}")] for tid, title in items]
    rows.append([InlineKeyboardButton("🔙 برگشت", callback_data="tpl:back")])
    return InlineKeyboardMarkup(rows)


def template_preview_kb(template_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ انتخاب این تمپلیت", callback_data=f"tpl:use:{template_id}")],
        [InlineKeyboardButton("🔙 برگشت به لیست", callback_data="tpl:list")],
    ])


def admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن تمپلیت", callback_data="adm:tpl:add")],
        [InlineKeyboardButton("📋 لیست تمپلیت‌ها", callback_data="adm:tpl:list")],
    ])


def admin_templates_manage_kb(items: list[tuple[int, str, bool]]):
    rows = []
    for tid, title, active in items:
        status = "✅" if active else "❌"
        rows.append([InlineKeyboardButton(f"{status} {title}", callback_data=f"adm:tpl:view:{tid}")])
    rows.append([InlineKeyboardButton("🔙 برگشت", callback_data="adm:back")])
    return InlineKeyboardMarkup(rows)


def admin_template_actions_kb(template_id: int, is_active: bool):
    toggle_text = "غیرفعال کن" if is_active else "فعال کن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔁 {toggle_text}", callback_data=f"adm:tpl:toggle:{template_id}")],
        [InlineKeyboardButton("🗑 حذف", callback_data=f"adm:tpl:del:{template_id}")],
        [InlineKeyboardButton("🔙 برگشت به لیست", callback_data="adm:tpl:list")],
    ])


def edit_images_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید عکس‌ها", callback_data="edit:images:confirm")],
        [InlineKeyboardButton("🗑 پاک کردن عکس‌ها", callback_data="edit:images:clear")],
        [InlineKeyboardButton("🔙 لغو", callback_data="edit:cancel")],
    ])


def edit_prompt_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 لغو", callback_data="edit:cancel")],
    ])


def edit_final_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 شروع پردازش", callback_data="edit:go")],
        [InlineKeyboardButton("🔙 لغو", callback_data="edit:cancel")],
    ])


def account_kb(lang: str):
    lang_label = "English 🇬🇧" if lang == "fa" else "فارسی 🇮🇷"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 تاریخچه آخر", callback_data="acc:history")],
        [InlineKeyboardButton(f"🌐 تغییر زبان به {lang_label}", callback_data="acc:lang:toggle")],
        [InlineKeyboardButton("🔙 برگشت", callback_data="acc:back")],
    ])
