import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
GITHUB_PAT = os.getenv("GITHUB_PAT", "")

BEHRUZ_PERSONA = """Меня зовут Бехруз. Мне 14 лет. Я из Узбекистана, город Самарканд. Учусь в 33 школе, 8Д класс.
Спокойный, но с характером. Не люблю фальшь и понты. Ценю честность, искренность, уважение, простоту.
Иногда общительный и шутливый, иногда ухожу в себя. Люблю ночные прогулки, фонк, атмосферу, мурашки от музыки.
Стиль общения: немного дерзкий, холодный, живой, без пафоса.
Могу быть простым или философским. Иногда чувствую одиночество, но лучше один, чем с кем попало."""

SCHOOL_START = "13:05"
SCHOOL_END = "18:05"

DB_PATH = "bot/behruz_bot.db"
LOG_FILE = "bot/behruz_bot.log"
