from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application

from services.queue import get_queue, EditJob

logger = logging.getLogger("worker")


async def _worker_loop(app: Application):
    q = get_queue()
    bot = app.bot

    logger.info("Worker started.")

    while True:
        job: EditJob = await q.get()
        try:
            # فعلاً AI واقعی وصل نیست، فقط ساختار صف و ارسال پیام آماده است.
            # مرحله بعد: دانلود فایل‌های تلگرام + ارسال به Gemini + دریافت تصویر + ارسال خروجی.
            await bot.send_message(
                chat_id=job.chat_id,
                text=(
                    f"🧩 Job #{job.request_id}\n"
                    f"📸 تصاویر: {len(job.image_file_ids)}\n"
                    f"📝 prompt: {job.prompt[:120]}{'...' if len(job.prompt) > 120 else ''}\n\n"
                    "✅ تو صف اجرا شد (AI رو مرحله بعد وصل می‌کنیم)."
                ),
            )
        except Exception:
            logger.exception("Worker job failed (request_id=%s)", job.request_id)
        finally:
            q.task_done()


async def start_worker(app: Application):
    # یک task پس‌زمینه داخل event loop همین bot
    if app.bot_data.get("worker_task"):
        return
    task = asyncio.create_task(_worker_loop(app))
    app.bot_data["worker_task"] = task
