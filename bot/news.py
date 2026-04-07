import httpx
import feedparser
import logging
import random

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://lenta.ru/rss/news",
    "https://www.rbc.ru/rss/news",
    "https://tass.ru/rss/v2.xml",
]


async def get_latest_news(count: int = 5) -> list[dict]:
    news_items = []
    feed_url = random.choice(RSS_FEEDS)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(feed_url)
            feed = feedparser.parse(resp.text)
            entries = feed.entries[:count]
            for entry in entries:
                news_items.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:200],
                    "link": entry.get("link", ""),
                })
    except Exception as e:
        logger.warning(f"Failed to fetch news from {feed_url}: {e}")

    if not news_items:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(RSS_FEEDS[0])
                feed = feedparser.parse(resp.text)
                for entry in feed.entries[:count]:
                    news_items.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:200],
                        "link": entry.get("link", ""),
                    })
        except Exception as e2:
            logger.warning(f"Fallback news also failed: {e2}")

    return news_items


def format_news_for_prompt(news_items: list[dict]) -> str:
    if not news_items:
        return ""
    lines = ["Актуальные новости:"]
    for i, item in enumerate(news_items[:3], 1):
        lines.append(f"{i}. {item['title']}")
    return "\n".join(lines)
