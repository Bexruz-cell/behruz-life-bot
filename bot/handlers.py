import logging
import asyncio
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import OWNER_ID, CHANNEL_ID
from bot import database as db
from bot.generator import generate_post, generate_life_event, generate_post_from_topic
from bot.photo import fetch_photo_bytes
from bot.poster import post_to_channel
from bot.keyboards import (
    main_menu, settings_menu, interval_menu,
    mood_menu, confirm_clear, templates_menu, back_to_main, preview_actions,
)

# Кэш последнего превью на пользователя {user_id: {text, photo_url, topic, mood}}
preview_cache: dict[int, dict] = {}

logger = logging.getLogger(__name__)
router = Router()


class States(StatesGroup):
    waiting_custom_topic = State()
    waiting_custom_message = State()
    waiting_event = State()
    waiting_phrase = State()
    waiting_photo_keywords = State()
    waiting_schedule_text = State()
    waiting_schedule_time = State()


def owner_only(func):
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id if hasattr(event, "from_user") else 0
        if user_id != OWNER_ID:
            return
        return await func(event, *args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


def build_status_text(bot_username: str = "") -> str:
    active = db.get_setting("active", "1")
    interval_min = int(db.get_setting("interval_min", "120"))
    interval_max = int(db.get_setting("interval_max", "240"))
    photo = db.get_setting("photo_mode", "1")
    total = db.get_posts_count()
    today = db.get_today_posts_count()
    category = db.get_setting("mood", "авто")

    last_post = db.get_last_post()
    last_time = last_post["created_at"] if last_post else "—"

    status_emoji = "✅" if active == "1" else "⏸"
    photo_emoji = "вкл" if photo == "1" else "выкл"

    def mins_to_str(m):
        if m < 60:
            return f"{m}мин"
        return f"{m // 60}ч"

    return (
        f"💀 <b>Dark News Bot — автопостер</b>\n"
        f"Хакинг · Даркнет · Крипта · Преступления\n\n"
        f"📢 Канал: <code>{CHANNEL_ID}</code>\n"
        f"🔄 Статус: {status_emoji} {'Активен' if active == '1' else 'Пауза'}\n"
        f"⏱ Интервал: {mins_to_str(interval_min)}–{mins_to_str(interval_max)}\n"
        f"🖼 Фото: {photo_emoji} | 📊 Всего: {total} · Сегодня: {today}\n"
        f"🕐 Последний пост: {last_time}\n"
        f"🗂 Категория: {category}"
    )


@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    db.add_log("command", "/start")
    active = db.get_setting("active", "1")
    text = build_status_text()
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_menu(active),
    )


@router.callback_query(F.data == "back_main")
async def cb_back_main(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    active = db.get_setting("active", "1")
    text = build_status_text()
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu(active))
    await cb.answer()


@router.callback_query(F.data == "post_now")
async def cb_post_now(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.answer("Публикую...")
    bot = cb.bot
    mood = db.get_setting("mood", "нейтральное")
    only_photo = db.get_setting("only_photo_mode", "0") == "1"
    continue_story = db.get_setting("continue_story_mode", "0") == "1"
    result = await post_to_channel(
        bot=bot, mood=mood,
        only_photo=only_photo,
        continue_story=continue_story,
    )
    if result:
        short = result["text"][:100]
        await cb.message.answer(f"✅ Запостили!\n\n{short}...")
    else:
        await cb.message.answer("❌ Ошибка при публикации")


@router.callback_query(F.data == "preview_post")
async def cb_preview(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.answer("⏳ Генерирую пост и картинку...")
    mood = db.get_setting("mood", "нейтральное")
    continue_story = db.get_setting("continue_story_mode", "0") == "1"

    # Генерируем пост
    result = await generate_post(mood=mood, continue_story=continue_story)
    text = result["text"]
    photo_url = result.get("photo_url", "")

    # Сохраняем в кэш для кнопки «Запостить»
    preview_cache[cb.from_user.id] = result

    preview_msg = f"👁 <b>Превью поста:</b>\n\n{text}\n\n<i>🖼 AI-картинка по теме: {result.get('topic', 'авто')}</i>"

    if photo_url:
        photo_bytes = await fetch_photo_bytes(photo_url)
        if photo_bytes:
            await cb.message.answer_photo(
                photo=BufferedInputFile(photo_bytes, filename="preview.jpg"),
                caption=f"👁 <b>Превью:</b>\n\n{text}"[:1024],
                parse_mode="HTML",
                reply_markup=preview_actions(),
            )
            return

    # Нет фото — шлём текстом
    await cb.message.answer(
        preview_msg[:4000],
        parse_mode="HTML",
        reply_markup=preview_actions(),
    )


@router.callback_query(F.data == "post_from_preview")
async def cb_post_from_preview(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    cached = preview_cache.get(cb.from_user.id)
    if not cached:
        # Кэш пустой — генерируем заново и постим
        await cb.answer("Кэш пустой, генерирую заново...")
        mood = db.get_setting("mood", "нейтральное")
        only_photo = db.get_setting("only_photo_mode", "0") == "1"
        result = await post_to_channel(bot=cb.bot, mood=mood, only_photo=only_photo)
        if result:
            await cb.message.answer(f"✅ Запостили!\n\n{result['text'][:150]}...")
        else:
            await cb.message.answer("❌ Ошибка публикации")
        return

    await cb.answer("✅ Публикую...")

    # Публикуем закэшированный пост
    text = cached["text"]
    photo_url = cached.get("photo_url", "")

    from bot.config import CHANNEL_ID as CH
    msg_id = None
    try:
        if photo_url:
            photo_bytes = await fetch_photo_bytes(photo_url)
            if photo_bytes:
                msg = await cb.bot.send_photo(
                    chat_id=CH,
                    photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                    caption=text[:1024],
                )
                msg_id = msg.message_id
        if not msg_id:
            msg = await cb.bot.send_message(chat_id=CH, text=text)
            msg_id = msg.message_id

        db.save_post(
            text=text,
            photo_url=photo_url,
            message_id=msg_id,
            topic=cached.get("topic"),
            mood=cached.get("mood"),
        )
        db.add_log("post_from_preview", f"chars={len(text)}")

        # Очищаем кэш
        preview_cache.pop(cb.from_user.id, None)

        await cb.message.answer(f"✅ <b>Запостили!</b>\n\n{text[:150]}...", parse_mode="HTML")
    except Exception as e:
        logger.error(f"post_from_preview error: {e}")
        await cb.message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data == "set_mood")
async def cb_set_mood(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("mood", "авто")
    await cb.message.edit_text(
        f"🗂 <b>Категория постов</b>\n\nТекущая: <i>{current}</i>\n\nВыбери тему:",
        parse_mode="HTML",
        reply_markup=mood_menu(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("mood_"))
async def cb_mood_set(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    mood = cb.data.replace("mood_", "")
    db.set_setting("mood", mood)
    db.add_log("category_changed", mood)
    active = db.get_setting("active", "1")
    await cb.message.edit_text(
        f"✅ Категория установлена: <b>{mood}</b>\n\n{build_status_text()}",
        parse_mode="HTML",
        reply_markup=main_menu(active),
    )
    await cb.answer()


@router.callback_query(F.data == "custom_topic")
async def cb_custom_topic(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        return
    await state.set_state(States.waiting_custom_topic)
    await cb.message.answer(
        "✏️ Введи тему (например: «взлом NASA», «кража $50M в крипте», «новый вирус»):",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.message(States.waiting_custom_topic)
async def handle_custom_topic(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    topic = message.text.strip()
    await state.clear()
    await message.answer("⏳ Генерирую пост на тему: " + topic)
    mood = db.get_setting("mood", "нейтральное")
    result = await post_to_channel(bot=message.bot, topic=topic, mood=mood)
    if result:
        await message.answer(f"✅ Пост опубликован!\n\n{result['text'][:150]}...")
    else:
        await message.answer("❌ Ошибка публикации")


@router.callback_query(F.data == "custom_message")
async def cb_custom_message(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        return
    await state.set_state(States.waiting_custom_message)
    await cb.message.answer(
        "💬 Напиши свой текст поста (опубликую как есть):",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.message(States.waiting_custom_message)
async def handle_custom_message(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    text = message.text.strip()
    await state.clear()
    bot = message.bot
    photo_url = ""
    if db.get_setting("photo_mode", "1") == "1":
        from bot.photo import generate_image_url
        mood = db.get_setting("mood", "нейтральное")
        photo_url = await generate_image_url(
            post_text=text,
            mood=mood,
            custom_keywords=db.get_setting("photo_keywords", "street night city teen"),
        )

    msg_id = None
    if photo_url:
        photo_bytes = await fetch_photo_bytes(photo_url)
        if photo_bytes:
            msg = await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                caption=text[:1024],
            )
            msg_id = msg.message_id
    if not msg_id:
        msg = await bot.send_message(chat_id=CHANNEL_ID, text=text)
        msg_id = msg.message_id

    db.save_post(text=text, photo_url=photo_url, message_id=msg_id)
    db.add_log("custom_post", text[:50])
    await message.answer(f"✅ Пост опубликован!")


@router.callback_query(F.data == "news_post")
async def cb_news_post(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.answer("Ищу новости...")
    mood = db.get_setting("mood", "нейтральное")
    result = await post_to_channel(bot=cb.bot, mood=mood, force_news=True)
    if result:
        await cb.message.answer(f"✅ Пост из новостей опубликован!\n\n{result['text'][:150]}...")
    else:
        await cb.message.answer("❌ Ошибка")


@router.callback_query(F.data == "history")
async def cb_history(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    posts = db.get_last_posts(20)
    if not posts:
        await cb.answer("История пустая")
        return
    lines = ["📋 <b>Последние посты:</b>\n"]
    for i, p in enumerate(posts, 1):
        short = p["text"][:60].replace("\n", " ")
        dt = p["created_at"][:16]
        lines.append(f"{i}. <i>{dt}</i>\n{short}...\n")
    text = "\n".join(lines)[:4000]
    await cb.message.answer(text, parse_mode="HTML", reply_markup=back_to_main())
    await cb.answer()


@router.callback_query(F.data == "stats")
async def cb_stats(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    total = db.get_posts_count()
    today = db.get_today_posts_count()
    avg_len = db.get_avg_post_length()
    events = db.get_today_events()
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"📝 Всего постов: <b>{total}</b>\n"
        f"📅 Сегодня: <b>{today}</b>\n"
        f"📏 Средняя длина: <b>{avg_len} символов</b>\n"
        f"📅 Событий сегодня: <b>{len(events)}</b>"
    )
    await cb.message.answer(text, parse_mode="HTML", reply_markup=back_to_main())
    await cb.answer()


@router.callback_query(F.data == "day_report")
async def cb_day_report(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    events = db.get_today_events()
    today_posts = db.get_last_posts(5)
    today_count = db.get_today_posts_count()
    mood = db.get_setting("mood", "нейтральное")

    text = (
        f"📝 <b>Что было сегодня</b>\n\n"
        f"🎭 Настроение: {mood}\n"
        f"📊 Постов сегодня: {today_count}\n\n"
    )
    if events:
        text += "📅 <b>События:</b>\n" + "\n".join(f"• {e}" for e in events) + "\n\n"
    else:
        text += "📅 Событий нет\n\n"

    if today_posts:
        text += "<b>Последние посты:</b>\n"
        for p in today_posts[:3]:
            text += f"— {p['text'][:60]}...\n"

    await cb.message.answer(text[:4000], parse_mode="HTML", reply_markup=back_to_main())
    await cb.answer()


@router.callback_query(F.data == "add_event")
async def cb_add_event(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        return
    await state.set_state(States.waiting_event)
    events = db.get_today_events()
    events_text = "\n".join(f"• {e}" for e in events) if events else "пусто"
    await cb.message.answer(
        f"📅 <b>Добавить событие дня</b>\n\nТекущие события:\n{events_text}\n\nНапиши новое событие:",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.message(States.waiting_event)
async def handle_event(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    event = message.text.strip()
    await state.clear()
    db.add_day_event(event)
    db.add_log("event_added", event)
    await message.answer(f"✅ Событие добавлено: <i>{event}</i>", parse_mode="HTML")


@router.callback_query(F.data == "settings")
async def cb_settings(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    school = "вкл" if db.get_setting("school_mode", "1") == "1" else "выкл"
    news = "вкл" if db.get_setting("news_mode", "0") == "1" else "выкл"
    photo = "вкл" if db.get_setting("photo_mode", "1") == "1" else "выкл"
    only_photo = "вкл" if db.get_setting("only_photo_mode", "0") == "1" else "выкл"
    story = "вкл" if db.get_setting("continue_story_mode", "0") == "1" else "выкл"
    interval_min = db.get_setting("interval_min", "120")
    interval_max = db.get_setting("interval_max", "240")

    text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"⏱ Интервал: {interval_min}–{interval_max} мин\n"
        f"📰 Режим новостей: {news}\n"
        f"🖼 Фото: {photo}\n"
        f"📷 Только фото: {only_photo}\n"
        f"📖 Режим продолжения: {story}"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=settings_menu())
    await cb.answer()


@router.callback_query(F.data == "toggle_active")
async def cb_toggle_active(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("active", "1")
    new_val = "0" if current == "1" else "1"
    db.set_setting("active", new_val)
    db.add_log("toggle_active", f"active={new_val}")
    active = db.get_setting("active", "1")
    state_text = "▶️ Запущен" if new_val == "1" else "⏸ На паузе"
    await cb.message.edit_text(
        f"{'▶️' if new_val == '1' else '⏸'} Бот {state_text}\n\n{build_status_text()}",
        parse_mode="HTML",
        reply_markup=main_menu(active),
    )
    await cb.answer()


@router.callback_query(F.data == "set_interval")
async def cb_set_interval(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.message.edit_text(
        "⏱ <b>Выбери интервал постинга:</b>",
        parse_mode="HTML",
        reply_markup=interval_menu(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("interval_"))
async def cb_interval_set(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    val = cb.data.replace("interval_", "")
    parts = val.split("_")
    interval_min, interval_max = parts[0], parts[1]
    db.set_setting("interval_min", interval_min)
    db.set_setting("interval_max", interval_max)
    db.add_log("interval_changed", f"{interval_min}-{interval_max} min")
    await cb.message.edit_text(
        f"✅ Интервал установлен: {interval_min}–{interval_max} минут",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.callback_query(F.data == "toggle_school")
async def cb_toggle_school(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("school_mode", "1")
    new_val = "0" if current == "1" else "1"
    db.set_setting("school_mode", new_val)
    status = "включён" if new_val == "1" else "выключен"
    await cb.answer(f"🏫 Режим школы {status}")
    await cb_settings(cb)


@router.callback_query(F.data == "toggle_news")
async def cb_toggle_news(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("news_mode", "0")
    new_val = "0" if current == "1" else "1"
    db.set_setting("news_mode", new_val)
    status = "включён" if new_val == "1" else "выключен"
    await cb.answer(f"📰 Режим новостей {status}")
    await cb_settings(cb)


@router.callback_query(F.data == "toggle_photo")
async def cb_toggle_photo(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("photo_mode", "1")
    new_val = "0" if current == "1" else "1"
    db.set_setting("photo_mode", new_val)
    status = "включено" if new_val == "1" else "выключено"
    await cb.answer(f"🖼 Фото {status}")
    await cb_settings(cb)


@router.callback_query(F.data == "toggle_only_photo")
async def cb_toggle_only_photo(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("only_photo_mode", "0")
    new_val = "0" if current == "1" else "1"
    db.set_setting("only_photo_mode", new_val)
    status = "включён" if new_val == "1" else "выключен"
    await cb.answer(f"📷 Режим 'только фото' {status}")
    await cb_settings(cb)


@router.callback_query(F.data == "toggle_story")
async def cb_toggle_story(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("continue_story_mode", "0")
    new_val = "0" if current == "1" else "1"
    db.set_setting("continue_story_mode", new_val)
    status = "включён" if new_val == "1" else "выключен"
    await cb.answer(f"📖 Режим истории {status}")
    await cb_settings(cb)


@router.callback_query(F.data == "set_photo_keywords")
async def cb_photo_keywords(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        return
    current = db.get_setting("photo_keywords", "street night city alone music teen")
    await state.set_state(States.waiting_photo_keywords)
    await cb.message.answer(
        f"🔑 <b>Ключевые слова для фото</b>\n\nТекущие: <i>{current}</i>\n\nВведи новые (на английском, через пробел):",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.message(States.waiting_photo_keywords)
async def handle_photo_keywords(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    keywords = message.text.strip()
    await state.clear()
    db.set_setting("photo_keywords", keywords)
    db.add_log("photo_keywords_changed", keywords)
    await message.answer(f"✅ Ключевые слова обновлены: <i>{keywords}</i>", parse_mode="HTML")


@router.callback_query(F.data == "add_phrase")
async def cb_add_phrase(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        return
    await state.set_state(States.waiting_phrase)
    phrases = db.get_custom_phrases()
    phrases_text = "\n".join(f"• {p}" for p in phrases[:5]) if phrases else "нет"
    await cb.message.answer(
        f"💬 <b>Добавить свою фразу</b>\n\nТекущие:\n{phrases_text}\n\nНапиши новую фразу:",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.message(States.waiting_phrase)
async def handle_phrase(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    phrase = message.text.strip()
    await state.clear()
    db.add_custom_phrase(phrase)
    db.add_log("phrase_added", phrase)
    await message.answer(f"✅ Фраза добавлена: <i>{phrase}</i>", parse_mode="HTML")


@router.callback_query(F.data == "schedule_post")
async def cb_schedule_post(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != OWNER_ID:
        return
    await state.set_state(States.waiting_schedule_text)
    await cb.message.answer(
        "📅 <b>Запланировать пост</b>\n\nВведи текст поста:",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.message(States.waiting_schedule_text)
async def handle_schedule_text(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    await state.update_data(schedule_text=message.text.strip())
    await state.set_state(States.waiting_schedule_time)
    await message.answer(
        "⏰ Теперь введи дату и время публикации в формате:\n<code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n\nПример: <code>08.04.2026 22:00</code>",
        parse_mode="HTML",
    )


@router.message(States.waiting_schedule_time)
async def handle_schedule_time(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    time_str = message.text.strip()
    data = await state.get_data()
    text = data.get("schedule_text", "")
    await state.clear()
    try:
        dt = datetime.strptime(time_str, "%d.%m.%Y %H:%M")
        scheduled_at = dt.strftime("%Y-%m-%d %H:%M")
        db.add_scheduled_post(text=text, photo_url="", scheduled_at=scheduled_at)
        db.add_log("post_scheduled", scheduled_at)
        await message.answer(f"✅ Пост запланирован на <b>{time_str}</b>", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Неверный формат. Используй: ДД.ММ.ГГГГ ЧЧ:ММ")


@router.callback_query(F.data == "random_event")
async def cb_random_event(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.answer("Генерирую событие...")
    event_text = await generate_life_event()
    db.add_day_event(event_text)
    await cb.message.answer(
        f"🎲 <b>Случайное событие:</b>\n\n{event_text}",
        parse_mode="HTML",
        reply_markup=back_to_main(),
    )


@router.callback_query(F.data == "export_json")
async def cb_export_json(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.answer("Экспортирую...")
    json_data = db.export_to_json()
    file_bytes = json_data.encode("utf-8")
    filename = f"behruz_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    await cb.message.answer_document(
        document=BufferedInputFile(file_bytes, filename=filename),
        caption="📦 Экспорт данных бота",
    )


@router.callback_query(F.data == "backup_db")
async def cb_backup_db(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.answer("Делаю backup...")
    from bot.config import DB_PATH
    try:
        with open(DB_PATH, "rb") as f:
            db_bytes = f.read()
        filename = f"behruz_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        await cb.message.answer_document(
            document=BufferedInputFile(db_bytes, filename=filename),
            caption="💾 Backup базы данных",
        )
    except Exception as e:
        await cb.message.answer(f"❌ Ошибка backup: {e}")


@router.callback_query(F.data == "show_logs")
async def cb_show_logs(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    logs = db.get_last_logs(20)
    if not logs:
        await cb.answer("Логи пустые")
        return
    lines = ["📜 <b>Последние действия:</b>\n"]
    for log in logs:
        lines.append(f"<i>{log['created_at'][5:16]}</i> — {log['action']}: {log['detail'] or ''}")
    await cb.message.answer("\n".join(lines)[:4000], parse_mode="HTML", reply_markup=back_to_main())
    await cb.answer()


@router.callback_query(F.data == "templates")
async def cb_templates(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.message.edit_text(
        "📋 <b>Быстрые шаблоны постов</b>\n\nВыбери тему:",
        parse_mode="HTML",
        reply_markup=templates_menu(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("template_"))
async def cb_template_post(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    category = cb.data.replace("template_", "")
    category_labels = {
        "hack": "взлом",
        "dark": "даркнет",
        "crypto": "крипта",
        "crime": "преступление",
        "leak": "утечка данных",
        "scam": "скам",
        "malware": "малварь",
        "breach": "взлом БД",
    }
    label = category_labels.get(category, category)
    await cb.answer(f"⏳ Ищу новость: {label}...")

    result = await generate_post_from_topic(label, category=category)
    if not result:
        await cb.message.answer("❌ Ошибка генерации")
        return

    text = result["text"]
    photo_url = result.get("photo_url", "")
    msg_id = None

    try:
        if photo_url:
            photo_bytes = await fetch_photo_bytes(photo_url)
            if photo_bytes:
                msg = await cb.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=BufferedInputFile(photo_bytes, filename="photo.jpg"),
                    caption=text[:1024],
                    parse_mode="HTML",
                )
                msg_id = msg.message_id
        if not msg_id:
            msg = await cb.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
            msg_id = msg.message_id

        db.save_post(text=text, photo_url=photo_url, message_id=msg_id, topic=label, mood=category)
        db.add_log("template_post", category)
        await cb.message.answer(f"✅ Пост <b>{label}</b> опубликован!", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Template post error: {e}")
        await cb.message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data == "clear_history")
async def cb_clear_history(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await cb.message.edit_text(
        "⚠️ <b>Очистить историю постов?</b>\n\nЭто действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=confirm_clear(),
    )
    await cb.answer()


@router.callback_query(F.data == "confirm_clear_yes")
async def cb_confirm_clear(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    db.clear_history()
    db.add_log("history_cleared", None)
    active = db.get_setting("active", "1")
    await cb.message.edit_text(
        f"✅ История очищена\n\n{build_status_text()}",
        parse_mode="HTML",
        reply_markup=main_menu(active),
    )
    await cb.answer()


@router.callback_query(F.data == "delete_last")
async def cb_delete_last(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    message_id = db.delete_last_post()
    if message_id:
        try:
            await cb.bot.delete_message(chat_id=CHANNEL_ID, message_id=message_id)
            await cb.answer("🗑 Пост удалён из канала")
        except Exception:
            await cb.answer("🗑 Запись удалена (пост мог быть удалён ранее)")
    else:
        await cb.answer("Нет постов для удаления")
    active = db.get_setting("active", "1")
    await cb.message.edit_text(
        build_status_text(),
        parse_mode="HTML",
        reply_markup=main_menu(active),
    )


@router.callback_query(F.data == "daily_report_now")
async def cb_daily_report_now(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        return
    await send_daily_report(cb.bot, cb.from_user.id)
    await cb.answer("Отчёт отправлен")


async def send_daily_report(bot: Bot, owner_id: int):
    total = db.get_posts_count()
    today = db.get_today_posts_count()
    avg_len = db.get_avg_post_length()
    events = db.get_today_events()
    mood = db.get_setting("mood", "нейтральное")

    text = (
        f"📊 <b>Ежедневный отчёт — {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
        f"📝 Постов сегодня: {today}\n"
        f"📊 Всего постов: {total}\n"
        f"📏 Средняя длина: {avg_len} символов\n"
        f"🎭 Настроение: {mood}\n"
    )
    if events:
        text += f"📅 События: {', '.join(events[:5])}\n"

    text += "\n💬 Как прошёл день? Что случилось сегодня?"

    await bot.send_message(owner_id, text, parse_mode="HTML")
    db.add_log("daily_report_sent", datetime.now().strftime("%d.%m.%Y"))
