import httpx
import logging
import random
from urllib.parse import quote

logger = logging.getLogger(__name__)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

CATEGORY_VISUALS = {
    "hack": [
        "black hooded hacker in dark room, multiple screens with green code, dramatic blue light",
        "close up hands typing on keyboard, dark room, code on screen, hacker aesthetic",
        "glowing skull on computer monitor, dark cyber room, neon green code rain",
        "anonymous mask on desk next to laptop, dark moody lighting",
        "server room at night, red emergency lights, cables everywhere",
    ],
    "dark": [
        "dark web concept, tor browser on screen, dark room, anonymous figure",
        "shadowy figure in hoodie browsing dark web on laptop, neon light",
        "underground network visualization, dark blue cyber space, hidden nodes",
        "encrypted messages on screen, dark corridor, mystery atmosphere",
    ],
    "crypto": [
        "bitcoin symbol burning in digital fire, dark background, dramatic lighting",
        "cryptocurrency exchange dashboard, red trading charts, hacker stealing crypto",
        "digital vault breaking open, coins spilling out, dark cyber space",
        "blockchain network visualization, gold coins falling, dark background",
        "laptop with crypto wallet app, hand reaching through screen stealing",
    ],
    "crime": [
        "handcuffs on keyboard, dark police lighting, crime scene tape",
        "police lights reflecting on wet street at night, dark atmosphere",
        "crime scene with laptop as evidence, forensic lighting",
        "shadowy criminal figure with briefcase, dark city alley, CCTV camera",
    ],
    "leak": [
        "open folder spilling documents into digital void, dark background",
        "database breach visualization, red warning screens, data pouring out",
        "leaked files concept, documents floating in dark space, warning signs",
    ],
    "scam": [
        "phishing hook through laptop screen, dark background, dramatic lighting",
        "fake website on screen, dark room, scammer at computer",
        "credit card on fishhook, dark cyber background",
    ],
    "malware": [
        "virus code spreading across screens, red warning alerts, dark room",
        "ransomware lock screen on computer, room in red light",
        "digital skull spreading through network cables, dark background",
        "infected computer with glowing red skull, dark server room",
    ],
    "breach": [
        "broken database icon leaking data streams, dark blue background",
        "cracked server with data spilling out, neon cyber aesthetic",
        "hacker accessing corporate database, red alert screens",
    ],
}

STYLE = "cinematic, dramatic lighting, high contrast, dark aesthetic, professional photo, 4k, no text, no watermark"


def get_visual_prompt(category: str, title: str = "") -> str:
    visuals = CATEGORY_VISUALS.get(category, CATEGORY_VISUALS["hack"])
    base = random.choice(visuals)
    return f"{base}, {STYLE}"


async def generate_image_url(post_text: str = "", topic: str = "",
                              mood: str = "", category: str = "hack",
                              custom_keywords: str = "") -> str:
    prompt = get_visual_prompt(category, post_text)
    encoded = quote(prompt)
    seed = random.randint(1, 99999)
    url = (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?width=1024&height=576&seed={seed}&nologo=true&model=flux"
    )
    logger.info(f"Image prompt [{category}]: {prompt[:100]}...")
    return url


async def fetch_photo_bytes(url: str) -> bytes | None:
    """Скачивает изображение — сначала пробует оригинальный URL (из новостей),
    потом Pollinations, потом Picsum."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(90.0, connect=15.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "image" in ct:
                    logger.info(f"Image OK: {len(resp.content)} bytes")
                    return resp.content
    except Exception as e:
        logger.warning(f"Image fetch error: {e}")

    # Picsum fallback
    try:
        fallback = f"https://picsum.photos/1024/576?random={random.randint(1,9999)}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(fallback)
            if resp.status_code == 200:
                return resp.content
    except Exception:
        pass

    return None


async def fetch_photo_url(keywords: str = "") -> str:
    return await generate_image_url(category="hack")
