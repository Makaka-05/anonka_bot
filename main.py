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
COOLDOWN = 5 

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()
user_last_time = {}

def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    conn.execute("CREATE TABLE IF NOT EXISTS replies (msg_id INTEGER PRIMARY KEY, author_id INTEGER)")
    conn.commit()
    conn.close()

def get_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Моя личная ссылка")], 
            [KeyboardButton(text="➕ Подключить группу")]
        ], 
        resize_keyboard=True
    )

def is_spam(uid):
    now = time.time()
    if uid in user_last_time and now - user_last_time[uid] < COOLDOWN:
        return True
    user_last_time[uid] = now
    return False

# --- ОБРАБОТЧИКИ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.chat.type != "private":
        return await message.answer("Кнопки работают только в ЛС бота!", reply_markup=ReplyKeyboardRemove())
    if is_spam(message.from_user.id): return
    init_db()
    await message.answer("Привет! Выбери действие:", reply_markup=get_kb())

@dp.message(F.text == "👤 Моя личная ссылка")
async def link(message: types.Message):
    if message.chat.type != "private":
        return await message.answer("Кнопки только в ЛС!", reply_markup=ReplyKeyboardRemove())
    if is_spam(message.from_user.id): return
    me = await bot.get_me()
    await message.answer(f"Твоя ссылка:\n<code>https://t.me/{me.username}?start={message.from_user.id}</code>")

@dp.message(F.text == "/setup")
async def setup(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        await message.answer("✅ Группа настроена. Кнопки скрыты.", reply_markup=ReplyKeyboardRemove())

@dp.message()
async def handle_messages(message: types.Message):
    # Антиспам только для ЛС
    if message.chat.type == "private" and is_spam(message.from_user.id): return

    # --- 1000% ЗАЩИТА ОТ ОШИБКИ ИЗ 80-Й СТРОКИ ---
    # Проверяем, что есть ответ, и что в ответе ЕСТЬ ТЕКСТ (не картинка, не кружок)
    if not message.reply_to_message or not message.reply_to_message.text:
        return 
    
    ref_text = message.reply_to_message.text

    # Поддерживаем и старый текст ("Анонимка в группу") и новый
    if "Напиши сообщение в ответ" in ref_text or "Анонимка в группу" in ref_text:
        target_ids = re.findall(r'-?\d+', ref_text)
        if target_ids:
            try:
                target = target_ids[0]
                sent = await bot.send_message(target, f"📩 <b>Анонимка:</b>\n\n{message.text}")
                if not str(target).startswith("-"):
                    conn = sqlite3.connect("anonymous_pro.db")
                    conn.execute("INSERT INTO replies VALUES (?, ?)", (sent.message_id, message.from_user.id))
                    conn.commit()
                    conn.close()
                await message.answer("✅ Отправлено!")
            except Exception as e: 
                await message.answer("❌ Ошибка доставки.")

    elif "Анонимка:" in ref_text:
        conn = sqlite3.connect("anonymous_pro.db")
        res = conn.execute("SELECT author_id FROM replies WHERE msg_id = ?", (message.reply_to_message.message_id,)).fetchone()
        conn.close()
        if res:
            try:
                await bot.send_message(res[0], f"💬 <b>Ответ:</b>\n\n{message.text}")
                await message.answer("✅ Доставлено!")
            except: 
                await message.answer("❌ Ошибка.")

async def main():
    # Эта строчка докажет, что новый код загрузился
    print("=== 1000% ВЕРСИЯ ЗАГРУЖЕНА УСПЕШНО ===")
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
