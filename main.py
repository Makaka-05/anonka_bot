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
COOLDOWN_SECONDS = 5 

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()
user_last_time = {}

def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    conn.execute("CREATE TABLE IF NOT EXISTS replies (msg_id INTEGER PRIMARY KEY, author_id INTEGER)")
    conn.commit()
    conn.close()

def get_main_kb():
    kb = [[KeyboardButton(text="👤 Моя личная ссылка")], [KeyboardButton(text="➕ Подключить группу")]]
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
    if message.chat.type != "private":
        await message.answer("Кнопки удалены. Используйте их в ЛС бота.", reply_markup=ReplyKeyboardRemove())
        return
    if is_spam(message.from_user.id): return
    init_db()
    await message.answer("Бот готов к работе. Выберите действие:", reply_markup=get_main_kb())

@dp.message(F.text == "👤 Моя личная ссылка")
async def show_link(message: types.Message):
    if message.chat.type != "private":
        await message.answer("Здесь кнопки не работают.", reply_markup=ReplyKeyboardRemove())
        return
    if is_spam(message.from_user.id): return
    me = await bot.get_me()
    await message.answer(f"Твоя ссылка: <code>https://t.me/{me.username}?start={message.from_user.id}</code>")

@dp.message(F.text == "/setup")
async def setup_group(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        await message.answer(f"✅ Настройка завершена. Кнопки в группе отключены.", reply_markup=ReplyKeyboardRemove())

@dp.message()
async def handle_all(message: types.Message):
    # Если спам в личке — игнорим
    if message.chat.type == "private" and is_spam(message.from_user.id): return

    # ИСПРАВЛЕНИЕ ОШИБКИ ИЗ ЛОГОВ (строка 80)
    # Проверяем: это ответ? У него есть текст?
    if not message.reply_to_message or not message.reply_to_message.text:
        return

    r_text = message.reply_to_message.text

    # Логика анонимного сообщения
    if "Напиши сообщение в ответ" in r_text:
        target_id = re.findall(r'-?\d+', r_text)
        if target_id:
            try:
                sent = await bot.send_message(target_id[0], f"📩 <b>Новое анонимное сообщение:</b>\n\n{message.text}")
                # Если это не группа, сохраняем для возможности ответа
                if not str(target_id[0]).startswith("-"):
                    conn = sqlite3.connect("anonymous_pro.db")
                    conn.execute("INSERT INTO replies VALUES (?, ?)", (sent.message_id, message.from_user.id))
                    conn.commit()
                    conn.close()
                await message.answer("✅ Сообщение доставлено!")
            except: 
                await message.answer("❌ Ошибка при отправке.")

    # Логика ответа на анонимку
    elif "Новое анонимное сообщение" in r_text:
        conn = sqlite3.connect("anonymous_pro.db")
        res = conn.execute("SELECT author_id FROM replies WHERE msg_id = ?", (message.reply_to_message.message_id,)).fetchone()
        conn.close()
        if res:
            try:
                await bot.send_message(res[0], f"💬 <b>Вам ответили:</b>\n\n{message.text}")
                await message.answer("✅ Ответ отправлен!")
            except: 
                await message.answer("❌ Ошибка при доставке ответа.")

async def main():
    print("--- СИСТЕМА ЗАПУЩЕНА БЕЗ ОШИБОК ---")
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
