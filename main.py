import asyncio
import sqlite3
import re
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.client.default import DefaultBotProperties

# --- НАСТРОЙКИ ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]
COOLDOWN_SECONDS = 5  # Твои законные 5 секунд

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Храним время последнего ответа юзеру
user_last_time = {}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS replies (msg_id INTEGER PRIMARY KEY, author_id INTEGER)")
    conn.commit()
    conn.close()

# Клавиатура (только для ЛС)
def get_main_kb(user_id):
    kb = [
        [KeyboardButton(text="👤 Моя личная ссылка")],
        [KeyboardButton(text="➕ Подключить группу")]
    ]
    if user_id in ADMIN_IDS:
        kb.append([KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Функция проверки задержки
def is_spam(user_id):
    curr = time.time()
    last = user_last_time.get(user_id, 0)
    if curr - last < COOLDOWN_SECONDS:
        return True
    user_last_time[user_id] = curr
    return False

# --- ОБРАБОТЧИКИ ---

@dp.message(CommandStart())
async def start(message: types.Message):
    # Если старт в группе — убираем кнопки и выходим
    if message.chat.type != "private":
        await message.answer("Бот работает! Кнопки доступны только в ЛС.", reply_markup=ReplyKeyboardRemove())
        return

    if is_spam(message.from_user.id): return
    
    init_db()
    args = message.text.split()
    if len(args) > 1:
        # Если пришли по ссылке (личной или групповой)
        await message.answer("🤫 Напиши сообщение в ответ на это сообщение (Reply), чтобы отправить его анонимно.")
    else:
        await message.answer("Привет! Управление ботом через кнопки ниже:", reply_markup=get_main_kb(message.from_user.id))

@dp.message(F.text == "👤 Моя личная ссылка")
async def my_link(message: types.Message):
    if message.chat.type != "private": return # Игнорим кнопки в группах
    if is_spam(message.from_user.id): return # Игнорим спам чаще 5 сек
    
    me = await bot.get_me()
    await message.answer(f"Твоя личная ссылка:\n<code>https://t.me/{me.username}?start={message.from_user.id}</code>")

@dp.message(F.text == "➕ Подключить группу")
async def group_link(message: types.Message):
    if message.chat.type != "private": return
    if is_spam(message.from_user.id): return
    
    await message.answer("Чтобы подключить группу:\n1. Добавь бота в админы группы.\n2. Напиши в группе команду /setup")

@dp.message(F.text == "/setup")
async def setup_group(message: types.Message):
    # Эта команда работает только в группах
    if message.chat.type in ["group", "supergroup"]:
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start={message.chat.id}"
        await message.answer(f"✅ <b>Группа подключена!</b>\n\nСсылка для анонимок в этот чат:\n<code>{link}</code>", reply_markup=ReplyKeyboardRemove())

@dp.message(F.text)
async def handle_msg(message: types.Message):
    # Задержка на любые текстовые сообщения
    if is_spam(message.from_user.id): return

    if not message.reply_to_message: return
    r_text = message.reply_to_message.text

    # Отправка анонимки
    if "Напиши сообщение в ответ" in r_text or "анонимно для ID" in r_text:
        # Извлекаем ID (если это личная анонимка)
        ids = re.findall(r'\d+', r_text)
        if ids:
            target_id = ids[0]
            try:
                sent = await bot.send_message(target_id, f"📩 <b>Новая анонимка:</b>\n\n{message.text}\n\n<i>(Ответь на это сообщение)</i>")
                # Сохраняем для возможности ответа
                conn = sqlite3.connect("anonymous_pro.db")
                conn.execute("INSERT INTO replies VALUES (?, ?)", (sent.message_id, message.from_user.id))
                conn.commit()
                conn.close()
                await message.answer("✅ Отправлено!")
            except:
                await message.answer("❌ Ошибка отправки.")

    # Ответ на анонимку
    elif "Новая анонимка" in r_text:
        conn = sqlite3.connect("anonymous_pro.db")
        res = conn.execute("SELECT author_id FROM replies WHERE msg_id = ?", (message.reply_to_message.message_id,)).fetchone()
        conn.close()
        if res:
            try:
                await bot.send_message(res[0], f"💬 <b>Тебе ответили:</b>\n\n{message.text}")
                await message.answer("✅ Ответ доставлен!")
            except:
                await message.answer("❌ Юзер закрыл бота.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
