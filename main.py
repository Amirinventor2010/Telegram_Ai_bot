from dotenv import load_dotenv
load_dotenv()

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters
)
from config import settings
from bot.states import States
from bot.handlers import (
    start,
    home_router,
    callbacks,
    admin_cmd,
    adm_tpl_title,
    adm_tpl_desc,
    adm_tpl_prompt,
    adm_tpl_sample,
    edit_receive_images,
    edit_receive_prompt,
)


def main():
    app = Application.builder().token(settings.BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.HOME: [
                CommandHandler("admin", admin_cmd),
                CallbackQueryHandler(callbacks),
                MessageHandler(filters.TEXT & ~filters.COMMAND, home_router),
            ],

            # Admin wizard
            States.ADM_TPL_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adm_tpl_title)
            ],
            States.ADM_TPL_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adm_tpl_desc)
            ],
            States.ADM_TPL_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adm_tpl_prompt)
            ],
            States.ADM_TPL_SAMPLE: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE | (filters.TEXT & ~filters.COMMAND), adm_tpl_sample)
            ],

            # Edit flow
            States.EDIT_WAIT_IMAGES: [
                CallbackQueryHandler(callbacks),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, edit_receive_images),
            ],
            States.EDIT_WAIT_PROMPT: [
                CallbackQueryHandler(callbacks),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_receive_prompt),
            ],
            States.EDIT_CONFIRM: [
                CallbackQueryHandler(callbacks),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        name="main_conversation",
        persistent=False,
    )

    app.add_handler(conv)

    print("✅ Bot is running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
