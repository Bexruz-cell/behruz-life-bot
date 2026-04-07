from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(status_text: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Запостить сейчас", callback_data="post_now"),
        InlineKeyboardButton(text="👁 Превью поста", callback_data="preview_post"),
    )
    builder.row(
        InlineKeyboardButton(text="🎭 Настроение", callback_data="set_mood"),
        InlineKeyboardButton(text="✏️ Своя тема", callback_data="custom_topic"),
    )
    builder.row(
        InlineKeyboardButton(text="📰 Пост из новостей", callback_data="news_post"),
        InlineKeyboardButton(text="💬 Своё сообщение", callback_data="custom_message"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 История постов", callback_data="history"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Что было сегодня", callback_data="day_report"),
        InlineKeyboardButton(text="📅 События", callback_data="add_event"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
        InlineKeyboardButton(text="⏸ Пауза" if status_text == "1" else "▶️ Запуск",
                             callback_data="toggle_active"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить последний", callback_data="delete_last"),
    )
    return builder.as_markup()


def settings_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏱ Интервал постинга", callback_data="set_interval"),
        InlineKeyboardButton(text="🏫 Режим школы", callback_data="toggle_school"),
    )
    builder.row(
        InlineKeyboardButton(text="📰 Реакции на новости", callback_data="toggle_news"),
        InlineKeyboardButton(text="🖼 Режим фото", callback_data="toggle_photo"),
    )
    builder.row(
        InlineKeyboardButton(text="📷 Только фото", callback_data="toggle_only_photo"),
        InlineKeyboardButton(text="📖 Продолжить историю", callback_data="toggle_story"),
    )
    builder.row(
        InlineKeyboardButton(text="🔑 Ключевые слова фото", callback_data="set_photo_keywords"),
        InlineKeyboardButton(text="💬 Добавить фразу", callback_data="add_phrase"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Запланировать пост", callback_data="schedule_post"),
        InlineKeyboardButton(text="🎲 Случайное событие", callback_data="random_event"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Экспорт JSON", callback_data="export_json"),
        InlineKeyboardButton(text="💾 Backup БД", callback_data="backup_db"),
    )
    builder.row(
        InlineKeyboardButton(text="📜 Логи", callback_data="show_logs"),
        InlineKeyboardButton(text="📋 Шаблоны", callback_data="templates"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Очистить историю", callback_data="clear_history"),
        InlineKeyboardButton(text="📊 Отчёт дня", callback_data="daily_report_now"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"),
    )
    return builder.as_markup()


def interval_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = [
        ("30мин–1ч", "30_60"),
        ("1ч–2ч", "60_120"),
        ("2ч–4ч", "120_240"),
        ("4ч–8ч", "240_480"),
        ("8ч–12ч", "480_720"),
        ("12ч–24ч", "720_1440"),
    ]
    for label, val in options:
        builder.button(text=label, callback_data=f"interval_{val}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="settings"))
    return builder.as_markup()


def mood_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    moods = [
        ("🔀 Авто (миксовать)", "авто"),
        ("🔴 Взломы",          "hack"),
        ("💀 Даркнет",         "dark"),
        ("💸 Крипта",          "crypto"),
        ("🔫 Преступления",    "crime"),
        ("📂 Утечки данных",   "leak"),
        ("🎭 Скам/Фишинг",     "scam"),
        ("☠️ Малварь",         "malware"),
    ]
    for label, val in moods:
        builder.button(text=label, callback_data=f"mood_{val}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()


def confirm_clear() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, очистить", callback_data="confirm_clear_yes"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="settings"),
    )
    return builder.as_markup()


def templates_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    templates = [
        ("🔴 Взлом",      "hack"),
        ("💀 Даркнет",    "dark"),
        ("💸 Крипта",     "crypto"),
        ("🔫 Преступление","crime"),
        ("📂 Утечка",     "leak"),
        ("🎭 Скам",       "scam"),
        ("☠️ Малварь",    "malware"),
        ("💣 Взлом БД",   "breach"),
    ]
    for label, val in templates:
        builder.button(text=label, callback_data=f"template_{val}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="settings"))
    return builder.as_markup()


def back_to_main() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Главное меню", callback_data="back_main")
    return builder.as_markup()


def preview_actions() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Запостить", callback_data="post_from_preview"),
        InlineKeyboardButton(text="🔄 Новое превью", callback_data="preview_post"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main"),
    )
    return builder.as_markup()
