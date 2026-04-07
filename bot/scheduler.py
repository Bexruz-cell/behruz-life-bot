import logging
import random
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot

from bot.config import OWNER_ID, SCHOOL_START, SCHOOL_END
from bot import database as db
from bot.poster import post_to_channel
from bot.handlers import send_daily_report

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Samarkand")


def get_next_interval_seconds() -> int:
    interval_min = int(db.get_setting("interval_min", "120"))
    interval_max = int(db.get_setting("interval_max", "240"))
    minutes = random.randint(interval_min, interval_max)
    return minutes * 60


async def auto_post_job(bot: Bot):
    if db.get_setting("active", "1") != "1":
        logger.debug("Bot paused, skipping auto post")
        return

    now = datetime.now()
    current_time = now.strftime("%H:%M")
    school_mode = db.get_setting("school_mode", "1") == "1"

    if school_mode and SCHOOL_START <= current_time <= SCHOOL_END:
        roll = random.random()
        if roll > 0.15:
            logger.debug("School time, skipping (with 85% chance)")
            return

    mood = db.get_setting("mood", "нейтральное")
    only_photo = db.get_setting("only_photo_mode", "0") == "1"
    continue_story = db.get_setting("continue_story_mode", "0") == "1"

    result = await post_to_channel(
        bot=bot, mood=mood,
        only_photo=only_photo,
        continue_story=continue_story,
    )
    if result:
        logger.info(f"Auto post success: {result['text'][:50]}")
    else:
        logger.error("Auto post failed")

    next_secs = get_next_interval_seconds()
    logger.info(f"Next post in {next_secs // 60} minutes")
    scheduler.reschedule_job(
        "auto_post",
        trigger=IntervalTrigger(seconds=next_secs),
    )


async def check_scheduled_posts(bot: Bot):
    pending = db.get_pending_scheduled_posts()
    for post in pending:
        try:
            from aiogram.types import BufferedInputFile
            from bot.photo import fetch_photo_bytes
            from bot.config import CHANNEL_ID

            text = post["text"]
            photo_url = post.get("photo_url", "")

            if photo_url:
                photo_bytes = await fetch_photo_bytes(photo_url)
                if photo_bytes:
                    await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                        caption=text[:1024],
                    )
                else:
                    await bot.send_message(chat_id=CHANNEL_ID, text=text)
            else:
                await bot.send_message(chat_id=CHANNEL_ID, text=text)

            db.mark_scheduled_done(post["id"])
            db.save_post(text=text, photo_url=photo_url)
            db.add_log("scheduled_post_sent", f"id={post['id']}")
            logger.info(f"Sent scheduled post id={post['id']}")
        except Exception as e:
            logger.error(f"Failed to send scheduled post {post['id']}: {e}")


async def daily_report_job(bot: Bot):
    await send_daily_report(bot, OWNER_ID)


async def checkpoint_job():
    db.add_log("checkpoint", f"auto checkpoint {datetime.now().strftime('%H:%M')}")
    logger.info("Checkpoint saved")


def setup_scheduler(bot: Bot):
    initial_interval = get_next_interval_seconds()

    scheduler.add_job(
        auto_post_job,
        trigger=IntervalTrigger(seconds=initial_interval),
        id="auto_post",
        kwargs={"bot": bot},
        replace_existing=True,
    )

    scheduler.add_job(
        check_scheduled_posts,
        trigger=IntervalTrigger(minutes=1),
        id="check_scheduled",
        kwargs={"bot": bot},
        replace_existing=True,
    )

    scheduler.add_job(
        daily_report_job,
        trigger=CronTrigger(hour=22, minute=0, timezone="Asia/Samarkand"),
        id="daily_report",
        kwargs={"bot": bot},
        replace_existing=True,
    )

    scheduler.add_job(
        checkpoint_job,
        trigger=IntervalTrigger(minutes=30),
        id="checkpoint",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started. First post in {initial_interval // 60} minutes")
