import asyncio
import sqlite3
import re
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

# --- НАСТРОЙКИ ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]
COOLDOWN_SECONDS = 5  # Твои 5 секунд

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Словарь для хранения времени последнего УСПЕШНОГО ответа бота юзеру
# {user_id: время_последнего_сообщения}
last_action_time = {}

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS replies (msg_id INTEGER PRIMARY KEY, author_id INTEGER)")
    conn.commit()
    conn.close()

def get_main_kb(user_id):
    kb = [[KeyboardButton(text="👤 Моя личная ссылка")], [KeyboardButton(text="➕ Подключить группу")]]
    if user_id in ADMIN_IDS: kb.append([KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Функция проверки: можно ли сейчас ответить этому юзеру?
def can_respond(user_id):
    current_time = time.time()
    last_time = last_action_time.get(user_id, 0)
    
    if current_time - last_time >= COOLDOWN_SECONDS:
        # Если 5 секунд прошло — разрешаем и обновляем время
        last_action_time[user_id] = current_time
        return True
    # Если 5 секунд еще не прошло — запрещаем
    return False

# --- ОБРАБОТЧИКИ ---

@dp.message(CommandStart())
async def start(message: types.Message):
    if not can_respond(message.from_user.id): return # Просто игнорим
    
    init_db()
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("-100"):
        await message.answer(f"🤫 <b>Анонимка в группу</b>\nНапиши сообщение в ответ на это.")
    elif len(args) > 1 and args[1].isdigit():
        await message.answer(f"🤫 Пиши анонимно для ID <code>{args[1] track}</code>\nВ ответ на это.")
    else:
        await message.answer("Привет! Кнопки ниже:", reply_markup=get_main_kb(message.from_user.id))

@dp.message(F.text == "👤 Моя личная ссылка")
async def show_my_link(message: types.Message):
    # Если тыкнет 10 раз — ответит только на 1-й раз, остальные 9 проигнорит
    if not can_respond(message.from_user.id):
        return
    
    me = await bot.get_me()
    await message.answer(f"Твоя ссылка:\n<code>https://t.me/{me.username}?start={message.from_user.id}</code>")

@dp.message(F.text == "➕ Подключить группу")
async def how_to_connect(message: types.Message):
    if not can_respond(message.from_user.id): return
    await message.answer("Добавь бота в админы и напиши /setup в группе.")

@dp.message(F.text == "/setup")
async def setup_group(message: types.Message):
    # В группах обычно антифлуд на команды не ставят, чтобы не тупило
    if message.chat.type in ["group", "supergroup"]:
        me = await bot.get_me()
        await message.answer(f"✅ Готово! Ссылка: <code>https://t.me/{me.username}?start={message.chat.id}</code>")

@dp.message(F.text)
async def handle_all_messages(message: types.Message):
    # Проверка задержки для любого текстового сообщения или ответа
    if not can_respond(message.from_user.id):
        return

    if not message.reply_to_message: return
    r_text = message.reply_to_message.text

    # ЛИЧНАЯ АНОНИМКА
    if "Пиши анонимно для ID" in r_text:
        target_id = re.findall(r'\d+', r_text)[0]
        try:
            sent = await bot.send_message(target_id, f"📩 <b>Анонимный вопрос:</b>\n\n{message.text}")
            conn = sqlite3.connect("anonymous_pro.db")
            conn.execute("INSERT INTO replies VALUES (?, ?)", (sent.message_id, message.from_user.id))
            conn.commit()
            conn.close()
            await message.answer("✅ Отправлено!")
        except: await message.answer("❌ Ошибка.")

    # ОТВЕТ НА ВОПРОС
    elif "Анонимный вопрос" in r_text:
        conn = sqlite3.connect("anonymous_pro.db")
        res = conn.execute("SELECT author_id FROM replies WHERE msg_id = ?", (message.reply_to_message.message_id,)).fetchone()
        conn.close()
        if res:
            try:
                await bot.send_message(res[0], f"💬 <b>Ответ:</b>\n\n{message.text}")
                await message.answer("✅ Ответ доставлен!")
            except: await message.answer("❌ Ошибка.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
