import asyncio
import sqlite3
import re
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.client.default import DefaultBotProperties

# --- КОНФИГ ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]
COOLDOWN = 5 # Секунды

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()
user_last_time = {} # Для задержки

def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    conn.execute("CREATE TABLE IF NOT EXISTS replies (msg_id INTEGER PRIMARY KEY, author_id INTEGER)")
    conn.commit()
    conn.close()

def get_kb():
    buttons = [[KeyboardButton(text="👤 Моя личная ссылка")], [KeyboardButton(text="➕ Подключить группу")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def is_spam(uid):
    now = time.time()
    if uid in user_last_time and now - user_last_time[uid] < COOLDOWN:
        return True
    user_last_time[uid] = now
    return False

# --- ОБРАБОТЧИКИ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Если старт в группе — удаляем кнопки принудительно
    if message.chat.type != "private":
        return await message.answer("Кнопки только в ЛС бота!", reply_markup=ReplyKeyboardRemove())

    if is_spam(message.from_user.id): return
    init_db()
    
    args = message.text.split()
    if len(args) > 1:
        await message.answer("🤫 Напиши сообщение в ответ на это (через Reply), чтобы отправить анонимно.")
    else:
        await message.answer("Привет! Управляй ботом кнопками ниже:", reply_markup=get_kb())

@dp.message(F.text == "👤 Моя личная ссылка")
async def link(message: types.Message):
    # Если нажали в группе (кнопка осталась в кэше) — стираем её
    if message.chat.type != "private":
        return await message.answer("Здесь кнопки не работают.", reply_markup=ReplyKeyboardRemove())
    
    if is_spam(message.from_user.id): return
    me = await bot.get_me()
    await message.answer(f"Твоя ссылка:\n<code>https://t.me/{me.username}?start={message.from_user.id}</code>")

@dp.message(F.text == "/setup")
async def setup(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        me = await bot.get_me()
        # При ответе в группе принудительно убираем кнопки у всех участников
        await message.answer(f"✅ Настроено! Ссылка для группы:\n<code>https://t.me/{me.username}?start={message.chat.id}</code>", reply_markup=ReplyKeyboardRemove())

@dp.message()
async def global_handler(message: types.Message):
    # Если это личка и спам — выходим
    if message.chat.type == "private" and is_spam(message.from_user.id): return

    # Проверка: это ответ на сообщение? Есть ли в нем текст?
    if not message.reply_to_message or not message.reply_to_message.text:
        return
    
    ref_text = message.reply_to_message.text

    # Логика отправки анонимки
    if "Напиши сообщение в ответ" in ref_text:
        target_ids = re.findall(r'-?\d+', ref_text)
        if target_ids:
            try:
                target = target_ids[0]
                sent = await bot.send_message(target, f"📩 <b>Новая анонимка:</b>\n\n{message.text or '[Медиа]'}")
                
                # Сохраняем для ответов, если это не группа
                if not str(target).startswith("-"):
                    conn = sqlite3.connect("anonymous_pro.db")
                    conn.execute("INSERT INTO replies VALUES (?, ?)", (sent.message_id, message.from_user.id))
                    conn.commit()
                    conn.close()
                await message.answer("✅ Отправлено!")
            except Exception:
                await message.answer("❌ Ошибка доставки.")

    # Логика ответа
    elif "Новая анонимка" in ref_text:
        conn = sqlite3.connect("anonymous_pro.db")
        res = conn.execute("SELECT author_id FROM replies WHERE msg_id = ?", (message.reply_to_message.message_id,)).fetchone()
        conn.close()
        if res:
            try:
                await bot.send_message(res[0], f"💬 <b>Тебе ответили:</b>\n\n{message.text or '[Медиа]'}")
                await message.answer("✅ Ответ доставлен!")
            except Exception:
                await message.answer("❌ Пользователь закрыл бота.")

async def main():
    print("!!! БОТ ЗАПУЩЕН С ФИЛЬТРОМ СПАМА !!!")
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
