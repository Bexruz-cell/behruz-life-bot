import httpx
import feedparser
import logging
import random
import re
from html import unescape

logger = logging.getLogger(__name__)

# Лучшие RSS источники по теме
RSS_FEEDS = {
    "hack": [
        ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
        ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
        ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
        ("Dark Reading", "https://www.darkreading.com/rss.xml"),
    ],
    "crypto": [
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Decrypt", "https://decrypt.co/feed"),
    ],
    "general": [
        ("Hacker News", "https://news.ycombinator.com/rss"),
        ("SecurityWeek", "https://feeds.feedburner.com/securityweek"),
        ("ThreatPost", "https://threatpost.com/feed/"),
    ],
}

ALL_FEEDS = [f for feeds in RSS_FEEDS.values() for f in feeds]

KEYWORDS_HACK = [
    "hack", "breach", "leak", "exploit", "ransomware", "malware",
    "phishing", "vulnerability", "stolen", "data breach", "darknet",
    "dark web", "cybercrime", "attack", "defaced", "backdoor",
    "взлом", "утечка", "хакер", "вирус", "атака", "кража"
]

KEYWORDS_CRYPTO = [
    "bitcoin", "crypto", "blockchain", "ethereum", "wallet", "defi",
    "nft", "rugpull", "scam", "stolen crypto", "exchange hack",
    "крипта", "биткоин", "мошенничество"
]

KEYWORDS_CRIME = [
    "murder", "killed", "arrested", "drug", "trafficking", "fraud",
    "stolen", "robbery", "cartel", "assassination", "убийство",
    "арест", "наркотики", "мошенник"
]


def clean_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    return unescape(text).strip()


def extract_image_from_entry(entry) -> str:
    # 1. Enclosure
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if 'image' in enc.get('type', ''):
                return enc.get('href', '')

    # 2. media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        for media in entry.media_content:
            if 'image' in media.get('type', ''):
                return media.get('url', '')

    # 3. media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url', '')
        if url:
            return url

    # 4. Из content/summary - ищем img src
    content = ''
    if hasattr(entry, 'content') and entry.content:
        content = entry.content[0].get('value', '')
    elif hasattr(entry, 'summary'):
        content = entry.summary or ''

    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        url = img_match.group(1)
        if url.startswith('http') and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            return url

    return ''


def detect_category(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    if any(k in text for k in ["ransomware", "malware", "trojan", "virus", "backdoor", "☠", "malwar"]):
        return "malware"
    if any(k in text for k in ["data breach", "database", "leaked", "exposed records", "утечка"]):
        return "breach"
    if any(k in text for k in ["dark web", "darknet", "tor ", "onion", "даркнет"]):
        return "dark"
    if any(k in text for k in ["bitcoin", "crypto", "ethereum", "wallet hack", "defi", "крипта", "биткоин"]):
        return "crypto"
    if any(k in text for k in ["scam", "phishing", "fraud", "mailing", "скам", "мошен"]):
        return "scam"
    if any(k in text for k in ["hack", "breach", "exploit", "vulnerab", "взлом", "атак"]):
        return "hack"
    if any(k in text for k in ["murder", "kill", "arrest", "drug", "cartel", "убийство", "арест"]):
        return "crime"
    return "hack"


async def fetch_feed(source_name: str, feed_url: str, count: int = 5) -> list[dict]:
    items = []
    try:
        async with httpx.AsyncClient(
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(feed_url)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:count]:
                title = clean_html(entry.get("title", ""))
                summary = clean_html(entry.get("summary", ""))[:500]
                link = entry.get("link", "")
                image_url = extract_image_from_entry(entry)
                category = detect_category(title, summary)

                if title:
                    items.append({
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": source_name,
                        "image_url": image_url,
                        "category": category,
                    })
    except Exception as e:
        logger.warning(f"Feed error [{source_name}]: {e}")
    return items


async def get_latest_news(count: int = 5, category: str = None) -> list[dict]:
    if category and category in RSS_FEEDS:
        feeds = RSS_FEEDS[category]
    else:
        feeds = random.sample(ALL_FEEDS, min(3, len(ALL_FEEDS)))

    all_items = []
    for source_name, feed_url in feeds[:2]:
        items = await fetch_feed(source_name, feed_url, count=8)
        all_items.extend(items)

    if not all_items:
        # Запасной вариант — общие новости
        for source_name, feed_url in RSS_FEEDS["general"][:2]:
            items = await fetch_feed(source_name, feed_url, count=5)
            all_items.extend(items)

    random.shuffle(all_items)
    return all_items[:count]


async def get_single_news_for_post() -> dict | None:
    """Возвращает одну свежую новость для оформления поста."""
    feeds_pool = ALL_FEEDS[:]
    random.shuffle(feeds_pool)

    for source_name, feed_url in feeds_pool[:4]:
        items = await fetch_feed(source_name, feed_url, count=10)
        if items:
            return random.choice(items[:5])

    return None


def format_news_for_prompt(news_items: list[dict]) -> str:
    if not news_items:
        return ""
    lines = ["Актуальные новости (используй как основу):"]
    for item in news_items[:3]:
        lines.append(f"— [{item['source']}] {item['title']}: {item['summary'][:150]}")
    return "\n".join(lines)
