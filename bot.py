import asyncio
import html
import logging
import os
import secrets
import sqlite3
from urllib.parse import quote, urlencode

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)

# Токен и id админа берутся из переменных окружения (их задают на хостинге),
# поэтому в этом файле ничего менять не нужно.
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not ADMIN_ID:
    raise SystemExit("Не заданы переменные окружения BOT_TOKEN и ADMIN_ID")

NOTICE = (
    "ℹ️ Получатель не увидит, кто написал сообщение. "
)

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# ---------- база данных ----------
db = sqlite3.connect("bot.db")
db.execute(
    "CREATE TABLE IF NOT EXISTS users ("
    "user_id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, username TEXT)"
)
db.execute(
    "CREATE TABLE IF NOT EXISTS sessions ("
    "sender_id INTEGER PRIMARY KEY, target_id INTEGER)"
)
db.execute("CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)")
db.commit()


def is_banned(user_id: int) -> bool:
    return db.execute("SELECT 1 FROM banned WHERE user_id=?", (user_id,)).fetchone() is not None


def register(user) -> str:
    """Создаёт пользователя (если нет) и возвращает его личный код."""
    row = db.execute("SELECT code FROM users WHERE user_id=?", (user.id,)).fetchone()
    if row:
        code = row[0]
        db.execute(
            "UPDATE users SET name=?, username=? WHERE user_id=?",
            (user.full_name, user.username, user.id),
        )
    else:
        code = secrets.token_urlsafe(6)
        db.execute(
            "INSERT INTO users (user_id, code, name, username) VALUES (?, ?, ?, ?)",
            (user.id, code, user.full_name, user.username),
        )
    db.commit()
    return code


def mention(user_id: int, name: str, username: str | None) -> str:
    text = f'<a href="tg://user?id={user_id}">{html.escape(name or "без имени")}</a>'
    if username:
        text += f" @{html.escape(username)}"
    return text


async def send_my_link(message: Message, bot: Bot, code: str):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"
    share = "https://t.me/share/url?" + urlencode(
        {"url": link, "text": "Напиши мне анонимно 👀"}, quote_via=quote
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Скопировать ссылку", copy_text=CopyTextButton(text=link))],
            [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share)],
            [
                InlineKeyboardButton(
                    text="👥 Добавить бота в чат",
                    url=f"https://t.me/{me.username}?startgroup=true",
                )
            ],
        ]
    )
    await message.answer(
        "Начни получать анонимные вопросы прямо сейчас 👀\n\n"
        "🔗 Ссылка для получения анонимных вопросов:\n\n"
        f"<code>{link}</code>\n\n"
        "Размести эту ссылку ☝️ в описании профиля, чтобы тебе могли написать.\n\n"
        f"{NOTICE}",
        reply_markup=kb,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


# ---------- /start ----------
@dp.message(CommandStart())
async def start(message: Message, command: CommandObject, bot: Bot):
    user = message.from_user
    if is_banned(user.id):
        return
    code = register(user)

    # Зашли по чужой ссылке
    if command.args:
        row = db.execute(
            "SELECT user_id FROM users WHERE code=?", (command.args,)
        ).fetchone()
        if not row:
            await message.answer("Ссылка недействительна.")
            return
        if row[0] != user.id:
            db.execute(
                "INSERT OR REPLACE INTO sessions (sender_id, target_id) VALUES (?, ?)",
                (user.id, row[0]),
            )
            db.commit()
            await message.answer(f"✍️ Напиши сообщение, и я передам его анонимно.\n\n{NOTICE}")
            return

    # Обычный /start — выдаём личную ссылку
    await send_my_link(message, bot, code)


# ---------- бота добавили в группу или канал ----------
@dp.my_chat_member()
async def added_to_chat(event: ChatMemberUpdated, bot: Bot):
    if event.chat.type not in ("group", "supergroup", "channel"):
        return
    old = event.old_chat_member.status
    new = event.new_chat_member.status
    if old not in ("left", "kicked") or new not in ("member", "administrator"):
        return

    user = event.from_user
    if is_banned(user.id):
        return
    code = register(user)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✉️ Написать анонимно", url=link)]]
    )
    try:
        await bot.send_message(
            event.chat.id,
            f"✉️ Анонимные сообщения для {html.escape(user.full_name)}\n\n"
            f"Нажми кнопку ниже и напиши.\n\n{NOTICE}",
            reply_markup=kb,
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        logging.warning("Не удалось написать в чат %s: нет прав", event.chat.id)


@dp.message(Command("unban"))
async def unban(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: /unban 123456789")
        return
    db.execute("DELETE FROM banned WHERE user_id=?", (int(command.args),))
    db.commit()
    await message.answer("Разбанен.")


@dp.message(Command("banned"))
async def banned_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    rows = db.execute(
        "SELECT b.user_id, u.name, u.username FROM banned b "
        "LEFT JOIN users u ON u.user_id = b.user_id"
    ).fetchall()
    if not rows:
        await message.answer("Список банов пуст.")
        return
    for user_id, name, username in rows:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Разбанить", callback_data=f"unban:{user_id}")]
            ]
        )
        await message.answer(
            f"🚫 {mention(user_id, name, username)} <code>{user_id}</code>",
            reply_markup=kb,
        )


@dp.callback_query(F.data.startswith("unban:"))
async def unban_button(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    user_id = int(callback.data.split(":")[1])
    db.execute("DELETE FROM banned WHERE user_id=?", (user_id,))
    db.commit()
    await callback.answer("Разбанен")
    await callback.message.edit_reply_markup(reply_markup=None)


# ---------- пересылка сообщений ----------
@dp.message(F.chat.type == "private")
async def relay(message: Message, bot: Bot):
    user = message.from_user
    if is_banned(user.id):
        return

    if message.text and message.text.startswith("/"):
        await message.answer("Неизвестная команда. Отправь /start, чтобы получить свою ссылку.")
        return

    row = db.execute(
        "SELECT target_id FROM sessions WHERE sender_id=?", (user.id,)
    ).fetchone()
    if not row:
        await message.answer(
            "Чтобы написать анонимно, перейди по чьей-нибудь ссылке.\n"
            "Свою ссылку можно получить командой /start."
        )
        return
    target_id = row[0]

    try:
        await bot.send_message(target_id, "📩 Новое анонимное сообщение:")
        await bot.copy_message(target_id, message.chat.id, message.message_id)
    except (TelegramForbiddenError, TelegramBadRequest):
        await message.answer("❌ Не удалось доставить: получатель остановил бота.")
        return

    # Лог для админа: кто -> кому (кликабельные имена)
    target = db.execute(
        "SELECT name, username FROM users WHERE user_id=?", (target_id,)
    ).fetchone()
    sender_text = mention(user.id, user.full_name, user.username)
    target_text = mention(target_id, target[0], target[1]) if target else str(target_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Забанить отправителя", callback_data=f"ban:{user.id}")]
        ]
    )
    try:
        await bot.send_message(
            ADMIN_ID,
            f"👁 {sender_text} <code>{user.id}</code> → {target_text}",
            reply_markup=kb,
        )
        await bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
    except (TelegramForbiddenError, TelegramBadRequest):
        logging.warning("Не могу написать админу. Открой бота и нажми /start с админ-аккаунта.")

    await message.answer("✅ Отправлено анонимно.")


# ---------- бан ----------
@dp.callback_query(F.data.startswith("ban:"))
async def ban(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    user_id = int(callback.data.split(":")[1])
    db.execute("INSERT OR IGNORE INTO banned (user_id) VALUES (?)", (user_id,))
    db.commit()
    await callback.answer("Забанен")
    await callback.message.edit_reply_markup(reply_markup=None)


async def main():
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
