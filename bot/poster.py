import logging
from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot.config import CHANNEL_ID
from bot import database as db
from bot.generator import generate_post
from bot.photo import fetch_photo_bytes

logger = logging.getLogger(__name__)


async def post_to_channel(bot: Bot, topic: str = None, mood: str = None,
                          force_news: bool = False, continue_story: bool = False,
                          only_photo: bool = False) -> dict | None:
    try:
        result = await generate_post(
            topic=topic, mood=mood,
            force_news=force_news,
            continue_story=continue_story,
        )
        text = result["text"]
        photo_url = result["photo_url"]

        message_id = None

        if only_photo and photo_url:
            photo_bytes = await fetch_photo_bytes(photo_url)
            if photo_bytes:
                msg = await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                    caption=text[:1024] if text else None,
                )
                message_id = msg.message_id
        elif photo_url:
            photo_bytes = await fetch_photo_bytes(photo_url)
            if photo_bytes:
                msg = await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                    caption=text[:1024],
                )
                message_id = msg.message_id
            else:
                msg = await bot.send_message(chat_id=CHANNEL_ID, text=text)
                message_id = msg.message_id
        else:
            msg = await bot.send_message(chat_id=CHANNEL_ID, text=text)
            message_id = msg.message_id

        db.save_post(
            text=text,
            photo_url=photo_url,
            message_id=message_id,
            topic=result.get("topic"),
            mood=result.get("mood"),
        )
        db.add_log("post_published", f"topic={result.get('topic')}, chars={len(text)}")
        logger.info(f"Posted to channel: {text[:50]}...")
        return result

    except Exception as e:
        logger.error(f"Failed to post to channel: {e}")
        db.add_log("post_error", str(e))
        return None
