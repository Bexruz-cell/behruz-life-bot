import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import TELEGRAM_BOT_TOKEN, OWNER_ID
from bot.database import init_db
from bot.handlers import router
from bot.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

log_dir = Path("bot")
log_dir.mkdir(exist_ok=True)

file_handler = logging.FileHandler("bot/behruz_bot.log", encoding="utf-8")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    init_db()
    logger.info("Database initialized")
    try:
        await bot.send_message(
            OWNER_ID,
            "🟢 <b>Behruz Life Bot запущен!</b>\n\nНапиши /start чтобы открыть меню.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not send startup message: {e}")
    setup_scheduler(bot)
    logger.info(f"Bot started. Owner: {OWNER_ID}")


async def on_shutdown(bot: Bot):
    from bot.scheduler import scheduler
    scheduler.shutdown(wait=False)
    logger.info("Bot stopped")
    try:
        await bot.send_message(OWNER_ID, "🔴 Бот остановлен")
    except Exception:
        pass


async def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        sys.exit(1)

    if not OWNER_ID:
        logger.error("OWNER_ID is not set!")
        sys.exit(1)

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.critical(f"Bot crashed: {e}. Restarting in 5 seconds...")
            import time
            time.sleep(5)
