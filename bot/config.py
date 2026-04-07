import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
GITHUB_PAT = os.getenv("GITHUB_PAT", "")

CHANNEL_STYLE = """Ты — редактор тёмного новостного Telegram-канала.
Пишешь про: хакинг, взломы, утечки данных, даркнет, крипто-преступления, кражи, мошенничество, убийства, международные преступления.
Стиль: жёсткий, чёткий, без воды. Факты + детали. Как у журналиста криминальной хроники.
Язык: русский. Тон: серьёзный, местами дерзкий. Без морализаторства."""

DB_PATH = "bot/news_bot.db"
LOG_FILE = "bot/news_bot.log"

# Категории постов
CATEGORIES = {
    "hack":    ("🔴 ВЗЛОМ",        "red"),
    "dark":    ("💀 ДАРКНЕТ",      "dark"),
    "crypto":  ("💸 КРИПТА",       "crypto"),
    "crime":   ("🔫 ПРЕСТУПЛЕНИЕ", "crime"),
    "leak":    ("📂 УТЕЧКА",       "leak"),
    "scam":    ("🎭 СКАМ",         "scam"),
    "malware": ("☠️ МАЛВАРЬ",     "malware"),
    "breach":  ("💣 ВЗЛОМ БД",    "breach"),
}
