import httpx
import logging
import random
from urllib.parse import quote

logger = logging.getLogger(__name__)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

# Позы силуэта по настроению
SILHOUETTE_POSES = {
    "грустное":    "silhouette of a teenage boy sitting on curb, head down, knees up",
    "злое":        "silhouette of a teenage boy standing with hands in pockets, tense posture, looking away",
    "спокойное":   "silhouette of a teenage boy leaning on wall, one foot up, relaxed",
    "скучно":      "silhouette of a teenage boy lying on bench, staring at sky",
    "кайфую":      "silhouette of a teenage boy with headphones, head tilted back, enjoying music",
    "задумчивое":  "silhouette of a teenage boy sitting on rooftop edge, looking at city lights",
    "уверенный":   "silhouette of a teenage boy walking confidently down empty street",
    "нейтральное": "silhouette of a teenage boy standing alone on street corner, hands in hoodie pocket",
}

# Фоны по теме
BACKGROUND_BY_TOPIC = {
    "ночная прогулка":   "night street Samarkand, warm streetlights, long road, atmospheric fog",
    "школа":             "empty school corridor at sunset, light through windows",
    "музыка":            "night city bokeh lights, warm orange glow, urban rooftop",
    "одиночество":       "empty dark alley, single streetlight, mist",
    "вечер":             "golden hour city skyline, warm haze, urban skyline Samarkand",
    "мысли":             "foggy bridge at night, reflective puddles, city glow",
    "курить":            "smoke curling in streetlight beam, dark night, urban backstreet",
    "прогулка":          "long empty street at night, perspective lines, distant lights",
    "самарканд":         "Registan blue tile domes at night, stars visible, ancient architecture",
    "закат":             "dramatic Central Asian sunset, orange purple sky, old city rooftops",
    "дождь":             "rain-soaked street, neon reflections in puddles, night",
    "новости":           "dark room lit by phone screen glow, night outside window",
}

STYLE_CORE = (
    "cinematic photography, moody film grain, "
    "high contrast, sharp silhouette, backlit, "
    "deep shadows, atmospheric, 4k quality, "
    "no face visible, dark aesthetic, teen vibes"
)


def get_pose(mood: str) -> str:
    return SILHOUETTE_POSES.get(mood, SILHOUETTE_POSES["нейтральное"])


def get_background(topic: str) -> str:
    for key, bg in BACKGROUND_BY_TOPIC.items():
        if key in topic.lower():
            return bg
    return "night city street Samarkand, ambient streetlights, urban atmosphere"


def build_image_prompt(post_text: str, topic: str = "",
                       mood: str = "нейтральное",
                       custom_keywords: str = "") -> str:

    pose = get_pose(mood)
    background = get_background(topic)

    # Иногда меняем ракурс для разнообразия
    angle = random.choice([
        "wide shot,",
        "low angle shot,",
        "from behind,",
        "side profile,",
        "dramatic backlit,",
    ])

    prompt = (
        f"{angle} {pose}, "
        f"{background}, "
        f"{STYLE_CORE}"
    )

    # Добавляем кастомные ключи если они не дефолтные
    if custom_keywords and "street night city alone music teen" not in custom_keywords:
        prompt += f", {custom_keywords}"

    return prompt[:450]


async def generate_image_url(post_text: str, topic: str = "",
                              mood: str = "нейтральное",
                              custom_keywords: str = "") -> str:
    prompt = build_image_prompt(post_text, topic, mood, custom_keywords)
    encoded = quote(prompt)
    seed = random.randint(1, 99999)
    url = (
        f"{POLLINATIONS_BASE}/{encoded}"
        f"?width=800&height=600&seed={seed}&nologo=true&model=flux"
    )
    logger.info(f"Image prompt: {prompt[:120]}...")
    return url


async def fetch_photo_bytes(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(90.0, connect=15.0)
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "image" in content_type:
                    logger.info(f"AI image generated OK ({len(resp.content)} bytes)")
                    return resp.content
                else:
                    logger.warning(f"Unexpected content-type: {content_type}")
            else:
                logger.warning(f"Pollinations failed: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"Pollinations error: {e}")

    # Фолбэк — Picsum
    try:
        seed = random.randint(1, 1000)
        fallback_url = f"https://picsum.photos/800/600?random={seed}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(fallback_url)
            if resp.status_code == 200:
                logger.info("Fallback: using Picsum image")
                return resp.content
    except Exception as e2:
        logger.warning(f"Picsum fallback failed: {e2}")

    return None


async def fetch_photo_url(keywords: str = "") -> str:
    return await generate_image_url(post_text="", custom_keywords=keywords)
