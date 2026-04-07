import httpx
import logging
import random
from datetime import datetime

from bot.config import MISTRAL_API_KEY, CHANNEL_STYLE, CATEGORIES
from bot import database as db
from bot.news import (
    get_latest_news, get_single_news_for_post,
    format_news_for_prompt, RSS_FEEDS,
)
from bot.photo import generate_image_url

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest"


POST_FORMAT_INSTRUCTIONS = """Оформи пост для Telegram-канала по этой новости.

СТРУКТУРА (строго соблюдай):
{КАТЕГОРИЯ_ЭМОДЗИ} {КАТЕГОРИЯ_НАЗВАНИЕ}

<b>{ЗАГОЛОВОК}</b>

{2-4 предложения с ключевыми фактами. Кто, что, где, когда, сколько. Никакой воды.}

📌 <b>Источник:</b> {название источника}
🔗 {ссылка}

ПРАВИЛА:
— Пиши только на русском
— Переведи и адаптируй с английского если нужно
— Факты точные, без выдумок
— Заголовок жёсткий и цепляющий
— Никаких хэштегов
— Никакого «по данным СМИ» и канцелярита
— Если есть цифры (сумма кражи, кол-во жертв) — обязательно укажи
— Максимум 200 слов"""

CATEGORY_LABELS = {
    "hack":    "🔴 ВЗЛОМ",
    "dark":    "💀 ДАРКНЕТ",
    "crypto":  "💸 КРИПТА",
    "crime":   "🔫 ПРЕСТУПЛЕНИЕ",
    "leak":    "📂 УТЕЧКА ДАННЫХ",
    "scam":    "🎭 СКАМ",
    "malware": "☠️ МАЛВАРЬ",
    "breach":  "💣 ВЗЛОМ БД",
}

MANUAL_TOPICS = [
    ("hack",   "масштабный взлом корпоративной сети"),
    ("dark",   "новый маркетплейс в даркнете"),
    ("crypto", "кража криптовалюты с биржи"),
    ("crime",  "арест хакера из группировки"),
    ("leak",   "утечка базы данных пользователей"),
    ("scam",   "масштабная фишинговая атака"),
    ("malware","новый вирус-шифровальщик"),
    ("breach", "взлом базы данных крупной компании"),
    ("crypto", "rug pull в DeFi проекте"),
    ("crime",  "ликвидация даркнет-маркетплейса"),
    ("hack",   "уязвимость нулевого дня"),
    ("crime",  "задержание кибер-преступной группировки"),
]


async def call_mistral(system: str, user: str, max_tokens: int = 500) -> str:
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
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                }
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Mistral error: {e}")
        return ""


def format_post_manually(news: dict) -> str:
    cat = news.get("category", "hack")
    label = CATEGORY_LABELS.get(cat, "🔴 ВЗЛОМ")
    title = news.get("title", "")
    summary = news.get("summary", "")[:300]
    source = news.get("source", "")
    link = news.get("link", "")

    text = f"{label}\n\n<b>{title}</b>\n\n{summary}"
    if source:
        text += f"\n\n📌 <b>Источник:</b> {source}"
    if link:
        text += f"\n🔗 {link}"
    return text


async def generate_post(topic: str = None, mood: str = None,
                        force_news: bool = True,
                        continue_story: bool = False,
                        category: str = None) -> dict:

    # Тянем реальную новость
    news = await get_single_news_for_post()

    # Если задан topic вручную — пробуем найти по теме
    if topic and not news:
        news_list = await get_latest_news(count=5)
        if news_list:
            news = news_list[0]

    cat = "hack"
    image_url = ""

    if news:
        cat = news.get("category", "hack")
        label = CATEGORY_LABELS.get(cat, "🔴 ВЗЛОМ")
        news_image = news.get("image_url", "")

        # Формируем промпт для Mistral
        user_prompt = (
            f"Новость:\n"
            f"Заголовок: {news['title']}\n"
            f"Описание: {news['summary']}\n"
            f"Источник: {news['source']}\n"
            f"Ссылка: {news['link']}\n\n"
            f"Категория поста: {label}\n\n"
            f"{POST_FORMAT_INSTRUCTIONS.replace('{КАТЕГОРИЯ_ЭМОДЗИ} {КАТЕГОРИЯ_НАЗВАНИЕ}', label)}"
        )

        text = await call_mistral(CHANNEL_STYLE, user_prompt, max_tokens=600)

        if not text:
            # Фолбэк — форматируем напрямую без Mistral
            text = format_post_manually(news)

        # Берём картинку из новости или генерируем AI
        if news_image and news_image.startswith("http"):
            image_url = news_image
            logger.info(f"Using news image: {news_image[:80]}")
        else:
            image_url = await generate_image_url(category=cat)

    else:
        # Нет новости — генерируем на случайную тему
        cat_key, fallback_topic = random.choice(MANUAL_TOPICS)
        cat = cat_key
        label = CATEGORY_LABELS.get(cat, "🔴 ВЗЛОМ")

        user_prompt = (
            f"Придумай и напиши правдоподобную новость на тему: «{topic or fallback_topic}».\n"
            f"Категория: {label}\n\n"
            f"{POST_FORMAT_INSTRUCTIONS}"
        )
        text = await call_mistral(CHANNEL_STYLE, user_prompt, max_tokens=600)

        if not text:
            text = f"{label}\n\n<b>Свежие новости из мира кибербезопасности</b>\n\nНет связи с источниками. Попробуй позже."

        image_url = await generate_image_url(category=cat)

    return {
        "text": text,
        "photo_url": image_url,
        "topic": topic or (news["title"][:50] if news else "авто"),
        "mood": cat,
        "category": cat,
        "news": news,
    }


async def generate_post_from_topic(topic: str, category: str = "hack") -> dict:
    """Генерирует пост по конкретной теме без RSS."""
    label = CATEGORY_LABELS.get(category, "🔴 ВЗЛОМ")
    user_prompt = (
        f"Напиши новостной пост для Telegram-канала на тему: «{topic}».\n"
        f"Категория: {label}\n\n"
        f"{POST_FORMAT_INSTRUCTIONS}"
    )
    text = await call_mistral(CHANNEL_STYLE, user_prompt, max_tokens=600)
    if not text:
        text = f"{label}\n\n<b>{topic}</b>\n\nИнформация по данной теме."

    image_url = await generate_image_url(category=category)
    return {
        "text": text,
        "photo_url": image_url,
        "topic": topic,
        "mood": category,
        "category": category,
        "news": None,
    }


async def generate_life_event() -> str:
    """Оставлено для совместимости — генерирует случайную криминальную новость."""
    cat_key, topic = random.choice(MANUAL_TOPICS)
    result = await generate_post_from_topic(topic, cat_key)
    return result["text"]
