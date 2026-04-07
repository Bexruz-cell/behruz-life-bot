import httpx
import logging
import random
from datetime import datetime

from bot.config import MISTRAL_API_KEY, BEHRUZ_PERSONA
from bot import database as db
from bot.news import get_latest_news, format_news_for_prompt
from bot.photo import generate_image_url

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"

TOPICS = [
    "ночная прогулка по Самарканду",
    "школа и одноклассники",
    "мысли перед сном",
    "музыка которую слушаю",
    "что раздражает в людях",
    "одиночество",
    "вечер дома",
    "воспоминание о чём-то",
    "наблюдение за городом",
    "случайная мысль",
    "настроение без причины",
    "лето и жара в Самарканде",
    "что думаю о жизни",
    "планы которые не сбылись",
    "момент из дня",
]

LIFE_EVENTS = [
    "поспорил с учителем",
    "нашёл крутой трек",
    "долго смотрел в окно",
    "чуть не опоздал на урок",
    "шёл домой один, думал о всяком",
    "слышал как соседи ругались",
    "видел красивый закат",
    "телефон завис в важный момент",
    "съел что-то невкусное",
    "кто-то написал странное",
    "долго не мог уснуть",
    "наблюдал за незнакомцем",
    "вспомнил что-то из детства",
    "устал и просто лежал",
]


def build_system_prompt(current_time: str, is_school: bool, last_posts: list,
                        events: list, news_text: str, mood: str,
                        custom_phrases: list, continue_story: bool) -> str:

    posts_summary = ""
    if last_posts:
        recent = last_posts[:10]
        posts_summary = "Последние посты (не повторяй темы и фразы):\n"
        for p in recent:
            short = p["text"][:80].replace("\n", " ")
            posts_summary += f"— {short}...\n"

    events_text = ""
    if events:
        events_text = f"\nСобытия сегодня: {', '.join(events)}"

    phrases_text = ""
    if custom_phrases:
        phrases_text = f"\nТвои личные фразы (используй иногда): {'; '.join(custom_phrases[:5])}"

    story_hint = ""
    if continue_story and last_posts:
        prev = last_posts[0]["text"][:100]
        story_hint = f"\nПродолжи историю из предыдущего поста: «{prev}...»"

    school_status = "ты сейчас на уроках" if is_school else "ты дома или на улице"

    prompt = f"""Ты — {BEHRUZ_PERSONA}

Сейчас: {current_time}. {school_status.capitalize()}.
Твоё настроение: {mood}.
{events_text}
{phrases_text}
{story_hint}

{posts_summary}

{news_text}

Напиши пост для своего Telegram-канала.
ПРАВИЛА:
- Пиши от первого лица, живым языком подростка
- Короткий или средний текст (2-8 предложений)
- Без хэштегов, без эмодзи в начале, без «пост», без «опубликовать»
- Иногда философский, иногда бытовой, иногда дерзкий
- Можно вопрос к читателям в конце
- НЕ повторяй темы из последних постов
- Будь живым, не пиши как робот
- Пиши только сам текст поста, ничего больше"""

    return prompt


async def generate_post(topic: str = None, mood: str = None,
                        force_news: bool = False,
                        continue_story: bool = False) -> dict:
    now = datetime.now()
    current_time = now.strftime("%d.%m.%Y %H:%M")

    from bot.config import SCHOOL_START, SCHOOL_END
    school_start = datetime.strptime(SCHOOL_START, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day)
    school_end = datetime.strptime(SCHOOL_END, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day)
    is_school = school_start <= now <= school_end and db.get_setting("school_mode", "1") == "1"

    if mood is None:
        mood = db.get_setting("mood", "нейтральное")

    last_posts = db.get_last_posts(10)
    events = db.get_today_events()
    custom_phrases = db.get_custom_phrases()

    news_text = ""
    if force_news or db.get_setting("news_mode", "0") == "1":
        news_items = await get_latest_news(3)
        news_text = format_news_for_prompt(news_items)

    if topic is None:
        if is_school:
            topic = random.choice([
                "скучно на уроке",
                "жду когда кончится",
                "думаю о своём пока учитель говорит",
            ])
        else:
            topic = random.choice(TOPICS)

    system_prompt = build_system_prompt(
        current_time=current_time,
        is_school=is_school,
        last_posts=last_posts,
        events=events,
        news_text=news_text,
        mood=mood,
        custom_phrases=custom_phrases,
        continue_story=continue_story,
    )

    user_message = f"Напиши пост на тему: {topic}" if topic else "Напиши пост"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                MISTRAL_API_URL,
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": 400,
                    "temperature": 0.85,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        text = random.choice([
            "просто сижу. ни о чём не думаю, просто существую.",
            "день прошёл как всегда. ничего особенного, но что-то зацепило.",
            "иногда лучше молчать. слова всё равно не передают то, что внутри.",
        ])

    photo_url = ""
    if db.get_setting("photo_mode", "1") == "1":
        custom_keywords = db.get_setting("photo_keywords", "street night city teen")
        photo_url = await generate_image_url(
            post_text=text,
            topic=topic or "",
            mood=mood,
            custom_keywords=custom_keywords,
        )
        logger.info(f"Generated image URL for post (topic={topic}, mood={mood})")

    return {
        "text": text,
        "photo_url": photo_url,
        "topic": topic,
        "mood": mood,
        "is_school": is_school,
    }


async def generate_life_event() -> str:
    event = random.choice(LIFE_EVENTS)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                MISTRAL_API_URL,
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": BEHRUZ_PERSONA},
                        {"role": "user",
                         "content": f"Опиши кратко жизненный эпизод: «{event}». 2-3 предложения от первого лица."},
                    ],
                    "max_tokens": 150,
                    "temperature": 0.9,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Life event generation error: {e}")
        return event
