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
COOLDOWN_SECONDS = 5 

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Хранилище времени последнего действия
user_last_time = {}

def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS replies (msg_id INTEGER PRIMARY KEY, author_id INTEGER)")
    conn.commit()
    conn.close()

def get_main_kb(user_id):
    kb = [[KeyboardButton(text="👤 Моя личная ссылка")], [KeyboardButton(text="➕ Подключить группу")]]
    if user_id in ADMIN_IDS:
        kb.append([KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

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
    # Если старт в группе — удаляем кнопки
    if message.chat.type != "private":
        await message.answer("Кнопки доступны только в ЛС бота.", reply_markup=ReplyKeyboardRemove())
        return

    if is_spam(message.from_user.id): return
    
    init_db()
    args = message.text.split()
    if len(args) > 1:
        await message.answer("🤫 Напиши сообщение в ответ на это (Reply), чтобы отправить его анонимно.")
    else:
        await message.answer("Привет! Используй кнопки ниже:", reply_markup=get_main_kb(message.from_user.id))

@dp.message(F.text == "👤 Моя личная ссылка")
async def my_link(message: types.Message):
    if message.chat.type != "private":
        await message.answer("Кнопки только для ЛС!", reply_markup=ReplyKeyboardRemove())
        return
    
    if is_spam(message.from_user.id): return
    me = await bot.get_me()
    await message.answer(f"Твоя ссылка:\n<code>https://t.me/{me.username}?start={message.from_user.id}</code>")

@dp.message(F.text == "/setup")
async def setup_group(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start={message.chat.id}"
        await message.answer(f"✅ Настроено!\nСсылка: <code>{link}</code>", reply_markup=ReplyKeyboardRemove())

@dp.message(F.text)
async def handle_msg(message: types.Message):
    # Если это личка и спам — игнорим
    if message.chat.type == "private" and is_spam(message.from_user.id):
        return

    # Защита от падения: проверяем, что это ВООБЩЕ ответ
    if not message.reply_to_message or not message.reply_to_message.text:
        return

    r_text = message.reply_to_message.text

    # Отправка анонимки
    if "Напиши сообщение в ответ" in r_text or "анонимно для ID" in r_text:
        ids = re.findall(r'-?\d+', r_text)
        if ids:
            target = ids[0]
            try:
                sent = await bot.send_message(target, f"📩 <b>Новая анонимка:</b>\n\n{message.text}\n\n<i>(Ответь на это сообщение)</i>")
                if not target.startswith("-"):
                    conn = sqlite3.connect("anonymous_pro.db")
                    conn.execute("INSERT INTO replies VALUES (?, ?)", (sent.message_id, message.from_user.id))
                    conn.commit()
                    conn.close()
                await message.answer("✅ Отправлено!")
            except:
                await message.answer("❌ Ошибка.")

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
                await message.answer("❌ Ошибка.")

async def main():
    print("--- БОТ ЗАПУЩЕН И ЗАЩИЩЕН ---")
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
