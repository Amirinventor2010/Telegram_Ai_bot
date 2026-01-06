from dotenv import load_dotenv
load_dotenv()

import asyncio
from telegram import Bot
from config import settings

async def main():
    bot = Bot(settings.BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook deleted + pending updates dropped")

if __name__ == "__main__":
    asyncio.run(main())
