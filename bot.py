import asyncio
import base64
import hashlib
import hmac
import html
import logging
import os
import sqlite3
import struct
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
# поэтому в этом файле токен и id вписывать не нужно.
BOT_TOKEN = os.getenv("BOT_TOKEN")
# ADMIN_ID — один id или несколько через запятую: 111111111,222222222
# Все они получают логи (кто кому написал) и могут банить/разбанивать.
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_ID", "").replace(" ", "").split(",") if x.isdigit()
}

if not BOT_TOKEN or not ADMIN_IDS:
    raise SystemExit("Не заданы переменные окружения BOT_TOKEN и ADMIN_ID")

# True  — сообщения для канала сначала приходят владельцу канала на проверку
#         (кнопки «Опубликовать» / «Отклонить»), это защита от спама и травли.
# False — сообщения публикуются в канале сразу.
MODERATION = True

NOTICE = (
    "ℹ️ Получатель не увидит, кто написал сообщение. "
)
NOTICE_CHANNEL = (
    "ℹ️ Твоё имя не будет опубликовано. "
)

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

# ---------- база данных ----------
db = sqlite3.connect("bot.db")
db.execute(
    "CREATE TABLE IF NOT EXISTS users ("
    "user_id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT, username TEXT)"
)
# target_id > 0 — личка пользователя, target_id < 0 — канал или группа
db.execute(
    "CREATE TABLE IF NOT EXISTS sessions ("
    "sender_id INTEGER PRIMARY KEY, target_id INTEGER)"
)
db.execute("CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)")
db.execute(
    "CREATE TABLE IF NOT EXISTS channels ("
    "chat_id INTEGER PRIMARY KEY, code TEXT UNIQUE, owner_id INTEGER, title TEXT)"
)
# очередь сообщений для канала: у каждого модератора своя копия с кнопками
db.execute(
    "CREATE TABLE IF NOT EXISTS pending ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, status TEXT DEFAULT 'new')"
)
db.execute(
    "CREATE TABLE IF NOT EXISTS pending_copies ("
    "pending_id INTEGER, reviewer_id INTEGER, message_id INTEGER)"
)
db.commit()


# ---------- постоянные ссылки ----------
# Код в ссылке содержит id владельца (зашифрован), поэтому ссылки работают
# даже если база bot.db на хостинге была стёрта при пересборке.
# LINK_SECRET — любая случайная строка (необязательная переменная окружения).
# Если её не задать, используется токен бота: при смене токена ссылки поменяются.
SECRET = (os.getenv("LINK_SECRET") or BOT_TOKEN).encode()


def _xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def make_code(kind: str, value: int) -> str:
    """kind: 'u' — пользователь, 'c' — канал или группа."""
    body = struct.pack(">q", value)
    tag = hmac.new(SECRET, b"n" + kind.encode() + body, hashlib.sha256).digest()[:6]
    stream = hmac.new(SECRET, b"s" + tag, hashlib.sha256).digest()[:8]
    raw = tag + _xor(body, stream)
    return kind + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def parse_code(code: str):
    """Возвращает (kind, value) или None, если код не наш."""
    if len(code) < 2 or code[0] not in ("u", "c"):
        return None
    try:
        raw = base64.urlsafe_b64decode(code[1:] + "=" * (-len(code[1:]) % 4))
    except Exception:
        return None
    if len(raw) != 14:
        return None
    kind = code[0]
    tag, enc = raw[:6], raw[6:]
    stream = hmac.new(SECRET, b"s" + tag, hashlib.sha256).digest()[:8]
    body = _xor(enc, stream)
    expected = hmac.new(SECRET, b"n" + kind.encode() + body, hashlib.sha256).digest()[:6]
    if not hmac.compare_digest(tag, expected):
        return None
    return kind, struct.unpack(">q", body)[0]


async def resolve_target(bot: Bot, arg: str):
    """По коду из ссылки возвращает (id получателя, название канала или None) либо None."""
    parsed = parse_code(arg)
    if parsed:
        kind, value = parsed
        if kind == "u":
            return value, None
        try:
            chat = await bot.get_chat(value)
        except (TelegramBadRequest, TelegramForbiddenError):
            return None
        return value, chat.title
    # старые ссылки, созданные до обновления (если база ещё жива)
    row = db.execute("SELECT user_id FROM users WHERE code=?", (arg,)).fetchone()
    if row:
        return row[0], None
    ch = db.execute("SELECT chat_id, title FROM channels WHERE code=?", (arg,)).fetchone()
    if ch:
        return ch[0], ch[1]
    return None


def is_banned(user_id: int) -> bool:
    return db.execute("SELECT 1 FROM banned WHERE user_id=?", (user_id,)).fetchone() is not None


def register(user) -> str:
    """Запоминает имя пользователя и возвращает его личный код."""
    code = make_code("u", user.id)
    db.execute(
        "INSERT INTO users (user_id, code, name, username) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username",
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
                    text="👥 Добавить бота в группу",
                    url=f"https://t.me/{me.username}?startgroup=true",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Добавить бота в канал",
                    url=f"https://t.me/{me.username}?startchannel=true&admin=post_messages",
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
        target = await resolve_target(bot, command.args)
        if target is None:
            await message.answer("Ссылка недействительна.")
            return
        target_id, title = target
        if target_id != user.id:
            db.execute(
                "INSERT OR REPLACE INTO sessions (sender_id, target_id) VALUES (?, ?)",
                (user.id, target_id),
            )
            db.commit()
            if target_id < 0:
                await message.answer(
                    f"✍️ Напиши сообщение — оно появится в «{html.escape(title or 'канале')}» "
                    f"без твоего имени.\n\n{NOTICE_CHANNEL}"
                )
            else:
                await message.answer(f"✍️ Напиши сообщение, и я передам его анонимно.\n\n{NOTICE}")
            return
        # это собственная ссылка — ниже покажем её

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
    register(user)

    title = event.chat.title or "канал"
    code = make_code("c", event.chat.id)
    db.execute(
        "INSERT INTO channels (chat_id, code, owner_id, title) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET owner_id=excluded.owner_id, title=excluded.title",
        (event.chat.id, code, user.id, title),
    )
    db.commit()

    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={code}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✉️ Написать анонимно", url=link)]]
    )
    when = "после проверки" if MODERATION else "сразу"
    try:
        await bot.send_message(
            event.chat.id,
            "✉️ Анонимные сообщения\n\n"
            f"Нажми кнопку ниже и напиши — сообщение появится здесь {when}, "
            "без твоего имени.\n\n"
            f"{NOTICE_CHANNEL}",
            reply_markup=kb,
        )
    except (TelegramForbiddenError, TelegramBadRequest):
        logging.warning("Не удалось написать в чат %s: нет прав", event.chat.id)


# ---------- админские команды ----------
@dp.message(Command("unban"))
async def unban(message: Message, command: CommandObject):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: /unban 123456789")
        return
    db.execute("DELETE FROM banned WHERE user_id=?", (int(command.args),))
    db.commit()
    await message.answer("Разбанен.")


@dp.message(Command("banned"))
async def banned_list(message: Message):
    if message.from_user.id not in ADMIN_IDS:
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
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    user_id = int(callback.data.split(":")[1])
    db.execute("DELETE FROM banned WHERE user_id=?", (user_id,))
    db.commit()
    await callback.answer("Разбанен")
    await callback.message.edit_reply_markup(reply_markup=None)


# ---------- доставка сообщений ----------
async def send_quoted(bot: Bot, target_id: int, message: Message):
    """Текст приходит в виде цитаты, остальное (фото, голосовые...) — заголовок и копия."""
    header = "🔔 У Вас новое сообщение!"
    if message.text and len(message.text) <= 3500:
        await bot.send_message(
            target_id, f"{header}\n\n<blockquote>{html.escape(message.text)}</blockquote>"
        )
    else:
        await bot.send_message(target_id, header)
        await bot.copy_message(target_id, message.chat.id, message.message_id)


async def deliver_to_user(message: Message, bot: Bot, target_id: int):
    """Личное сообщение владельцу ссылки. Возвращает (ответ, получатель для лога) или None."""
    try:
        await send_quoted(bot, target_id, message)
    except (TelegramForbiddenError, TelegramBadRequest):
        await message.answer("❌ Не удалось доставить: получатель остановил бота.")
        return None
    target = db.execute(
        "SELECT name, username FROM users WHERE user_id=?", (target_id,)
    ).fetchone()
    target_text = (
        mention(target_id, target[0], target[1])
        if target
        else mention(target_id, "получатель", None)
    )
    return "✅ Отправлено анонимно.", target_text


async def deliver_to_chat(message: Message, bot: Bot, chat_id: int):
    """Сообщение для канала или группы. Возвращает (ответ, получатель для лога) или None."""
    ch = db.execute(
        "SELECT owner_id, title FROM channels WHERE chat_id=?", (chat_id,)
    ).fetchone()
    owner_id, title = ch if ch else (None, None)
    if title is None:
        try:
            title = (await bot.get_chat(chat_id)).title
        except (TelegramBadRequest, TelegramForbiddenError):
            await message.answer("❌ Этот канал больше недоступен.")
            return None
    title_text = html.escape(title or "канал")
    target_text = f"канал «{title_text}»"

    if not MODERATION:
        try:
            await bot.copy_message(chat_id, message.chat.id, message.message_id)
        except (TelegramForbiddenError, TelegramBadRequest):
            await message.answer("❌ Сейчас не получилось отправить. Попробуй позже.")
            return None
        return "✅ Опубликовано анонимно.", target_text

    # Проверка: сообщение с кнопками получают все админы бота и владелец канала
    cur = db.execute("INSERT INTO pending (chat_id) VALUES (?)", (chat_id,))
    pid = cur.lastrowid
    db.commit()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"pub:{pid}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej:{pid}"),
            ]
        ]
    )
    delivered = 0
    for reviewer_id in ADMIN_IDS | ({owner_id} if owner_id else set()):
        try:
            await bot.send_message(
                reviewer_id, f"📥 Новое сообщение для «{title_text}», ждёт проверки:"
            )
            copy = await bot.copy_message(
                reviewer_id, message.chat.id, message.message_id, reply_markup=kb
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            continue
        db.execute(
            "INSERT INTO pending_copies (pending_id, reviewer_id, message_id) VALUES (?, ?, ?)",
            (pid, reviewer_id, copy.message_id),
        )
        delivered += 1
    db.commit()
    if not delivered:
        db.execute("DELETE FROM pending WHERE id=?", (pid,))
        db.commit()
        await message.answer("❌ Сейчас не получилось отправить. Попробуй позже.")
        return None
    return (
        "✅ Отправлено на проверку. Если модератор одобрит, сообщение появится в канале.",
        target_text,
    )


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

    if target_id < 0:
        result = await deliver_to_chat(message, bot, target_id)
    else:
        result = await deliver_to_user(message, bot, target_id)
    if result is None:
        return
    reply, target_text = result

    # Лог для админа: кто -> кому (кликабельные имена)
    sender_text = mention(user.id, user.full_name, user.username)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Забанить отправителя", callback_data=f"ban:{user.id}")]
        ]
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"👁 {sender_text} <code>{user.id}</code> → {target_text}",
                reply_markup=kb,
            )
            await bot.copy_message(admin_id, message.chat.id, message.message_id)
        except (TelegramForbiddenError, TelegramBadRequest):
            logging.warning(
                "Не могу написать модератору %s: пусть откроет бота и нажмёт /start.", admin_id
            )

    await message.answer(reply)


# ---------- проверка сообщений для канала ----------
def can_moderate(user_id: int, chat_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    row = db.execute("SELECT owner_id FROM channels WHERE chat_id=?", (chat_id,)).fetchone()
    return bool(row and row[0] == user_id)


async def close_pending(bot: Bot, pid: int, label: str):
    """Заменяет кнопки на итог у всех модераторов, чтобы никто не нажал второй раз."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label[:60], callback_data="noop")]]
    )
    rows = db.execute(
        "SELECT reviewer_id, message_id FROM pending_copies WHERE pending_id=?", (pid,)
    ).fetchall()
    for reviewer_id, message_id in rows:
        try:
            await bot.edit_message_reply_markup(
                chat_id=reviewer_id, message_id=message_id, reply_markup=kb
            )
        except (TelegramForbiddenError, TelegramBadRequest):
            pass


@dp.callback_query(F.data.startswith("pub:"))
async def publish(callback: CallbackQuery, bot: Bot):
    pid = int(callback.data.split(":")[1])
    row = db.execute("SELECT chat_id FROM pending WHERE id=?", (pid,)).fetchone()
    if not row:
        await callback.answer("Эта кнопка устарела.", show_alert=True)
        return
    chat_id = row[0]
    if not can_moderate(callback.from_user.id, chat_id):
        await callback.answer()
        return
    cur = db.execute(
        "UPDATE pending SET status='published' WHERE id=? AND status='new'", (pid,)
    )
    db.commit()
    if cur.rowcount == 0:
        await callback.answer("Уже обработано другим модератором.", show_alert=True)
        return
    try:
        await bot.copy_message(chat_id, callback.message.chat.id, callback.message.message_id)
    except (TelegramForbiddenError, TelegramBadRequest):
        db.execute("UPDATE pending SET status='new' WHERE id=?", (pid,))
        db.commit()
        await callback.answer(
            "Не удалось опубликовать. Проверь, что бот админ канала с правом публикации.",
            show_alert=True,
        )
        return
    await callback.answer("Опубликовано")
    await close_pending(bot, pid, f"✅ Опубликовано — {callback.from_user.full_name}")


@dp.callback_query(F.data.startswith("rej:"))
async def reject(callback: CallbackQuery, bot: Bot):
    pid = int(callback.data.split(":")[1])
    row = db.execute("SELECT chat_id FROM pending WHERE id=?", (pid,)).fetchone()
    if not row:
        await callback.answer("Эта кнопка устарела.", show_alert=True)
        return
    if not can_moderate(callback.from_user.id, row[0]):
        await callback.answer()
        return
    cur = db.execute(
        "UPDATE pending SET status='rejected' WHERE id=? AND status='new'", (pid,)
    )
    db.commit()
    if cur.rowcount == 0:
        await callback.answer("Уже обработано другим модератором.", show_alert=True)
        return
    await callback.answer("Отклонено")
    await close_pending(bot, pid, f"❌ Отклонено — {callback.from_user.full_name}")


@dp.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


# ---------- бан ----------
@dp.callback_query(F.data.startswith("ban:"))
async def ban(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
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
