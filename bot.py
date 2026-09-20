import asyncio
import html
import logging
import os
import secrets
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
    "Сообщения сохраняются для модерации (защита от спама и травли)."
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


MAIN_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📩 В ЛС", callback_data="menu:dm"),
            InlineKeyboardButton(text="👥 В группу", callback_data="menu:group"),
        ]
    ]
)


# ---------- /start ----------
@dp.message(CommandStart())
async def start(message: Message, command: CommandObject):
    user = message.from_user
    if is_banned(user.id):
        return
    register(user)

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

    # Обычный /start — главное меню
    await message.answer(
        "👋 Здесь можно получать анонимные сообщения.\n\n"
        "Куда подключить бота?\n\n"
        f"{NOTICE}",
        reply_markup=MAIN_KB,
    )


@dp.callback_query(F.data.startswith("menu:"))
async def menu(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    if is_banned(user.id):
        await callback.answer()
        return
    code = register(user)
    me = await bot.get_me()
    action = callback.data.split(":")[1]

    if action == "dm":
        link = f"https://t.me/{me.username}?start={code}"
        await callback.message.answer(
            f"📩 Твоя личная ссылка:\n{link}\n\n"
            "Повесь её в описание профиля. Кто перейдёт по ней, сможет написать "
            "тебе анонимно.\n\n"
            f"{NOTICE}"
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Добавить в группу",
                        url=f"https://t.me/{me.username}?startgroup=true",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="➕ Добавить в канал",
                        url=f"https://t.me/{me.username}?startchannel=true&admin=post_messages",
                    )
                ],
            ]
        )
        await callback.message.answer(
            "👥 Добавь бота в свою группу или канал. Он сам опубликует там сообщение "
            "с кнопкой «Написать анонимно», которая ведёт на твою личную ссылку.\n\n"
            "Для канала бот должен быть админом с правом публикации "
            "(это выбирается при добавлении).",
            reply_markup=kb,
        )
    await callback.answer()


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


# ---------- пересылка сообщений ----------
@dp.message(F.chat.type == "private")
async def relay(message: Message, bot: Bot):
    user = message.from_user
    if is_banned(user.id):
        return

    if message.text and message.text.startswith("/"):
        await message.answer("Неизвестная команда. Отправь /start, чтобы открыть меню.")
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
        await bot.send_message(ADMIN_ID, f"👁 {sender_text} → {target_text}", reply_markup=kb)
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
