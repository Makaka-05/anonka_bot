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

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    # Новая таблица для ответов: связываем ID сообщения у получателя с ID анонима
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS replies 
        (msg_id INTEGER PRIMARY KEY, author_id INTEGER)
    """)
    conn.commit()
    conn.close()

def get_main_kb(user_id):
    kb = [[KeyboardButton(text="👤 Моя личная ссылка")], [KeyboardButton(text="➕ Подключить группу")]]
    if user_id in ADMIN_IDS: kb.append([KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def notify_admins(message, mode, target_user=None):
    u = message.from_user
    sender_link = f"<a href='tg://user?id={u.id}'>{u.full_name}</a>"
    sender_un = f" (@{u.username})" if u.username else ""
    target_info = ""
    if target_user:
        t_link = f"<a href='tg://user?id={target_user.id}'>{target_user.full_name}</a>"
        target_info = f"\n🎯 <b>Кому:</b> {t_link}"

    log = f"🕵️ <b>ЛОГ</b>\n👤 <b>От:</b> {sender_link}{sender_un}\n📍 <b>Тип:</b> {mode}{target_info}\n📝 <b>Текст:</b> {message.text}"
    for admin_id in ADMIN_IDS:
        try: await bot.send_message(admin_id, log)
        except: pass

# --- ОБРАБОТКА КОМАНД ---

@dp.message(CommandStart())
async def start(message: types.Message):
    init_db()
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("-100"):
        await message.answer(f"🤫 <b>Анонимка в группу</b>\n\nНапиши сообщение (нажми 'Ответить'), и я его опубликую!\n🆔: <code>{args[1]}</code>")
    elif len(args) > 1 and args[1].isdigit():
        await message.answer(f"🤫 Пиши анонимно для ID <code>{args[1]}</code>\n\n(Нажми 'Ответить')")
    else:
        await message.answer("Привет! Выбери действие:", reply_markup=get_main_kb(message.from_user.id))

@dp.message(F.text == "/setup")
async def setup_group(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        me = await bot.get_me()
        await message.answer(f"✅ Группа готова!\nСсылка: <code>https://t.me/{me.username}?start={message.chat.id}</code>")

@dp.message(F.text == "👤 Моя личная ссылка")
async def show_my_link(message: types.Message):
    me = await bot.get_me()
    await message.answer(f"Твоя ссылка:\n<code>https://t.me/{me.username}?start={message.from_user.id}</code>")

# --- ГЛАВНЫЙ ОБРАБОТЧИК ---

@dp.message(F.text)
async def handle_all_messages(message: types.Message):
    if not message.reply_to_message: return
    reply_text = message.reply_to_message.text

    # 1. ОТПРАВКА В ГРУППУ
    if "Анонимка в группу" in reply_text:
        try:
            target_group = re.findall(r'-100\d+', reply_text)[0]
            await bot.send_message(target_group, f"📥 <b>Анонимно:</b>\n\n{message.text}")
            await message.answer("✅ Опубликовано!")
            await notify_admins(message, f"ГРУППА {target_group}")
        except: await message.answer("❌ Ошибка группы.")

    # 2. ЛИЧНАЯ ОТПРАВКА (Аноним пишет пользователю)
    elif "Пиши анонимно для ID" in reply_text:
        target_id = re.findall(r'\d+', reply_text)[0]
        try:
            sent_msg = await bot.send_message(target_id, f"📩 <b>Новый анонимный вопрос:</b>\n\n{message.text}\n\n<i>(Чтобы ответить, нажми 'Ответить' на это сообщение)</i>")
            
            # ЗАПОМИНАЕМ КТО НАПИСАЛ (для ответа)
            conn = sqlite3.connect("anonymous_pro.db")
            conn.execute("INSERT INTO replies VALUES (?, ?)", (sent_msg.message_id, message.from_user.id))
            conn.commit()
            conn.close()

            await message.answer("✅ Доставлено!")
            target_chat = await bot.get_chat(target_id)
            await notify_admins(message, "ЛИЧНО", target_user=target_chat)
        except: await message.answer("❌ Ошибка доставки.")

    # 3. ОТВЕТ НА АНОНИМКУ (Пользователь отвечает анониму)
    elif "Новый анонимный вопрос" in reply_text:
        conn = sqlite3.connect("anonymous_pro.db")
        res = conn.execute("SELECT author_id FROM replies WHERE msg_id = ?", (message.reply_to_message.message_id,)).fetchone()
        conn.close()

        if res:
            try:
                await bot.send_message(res[0], f"💬 <b>Тебе пришел ответ на твой вопрос:</b>\n\n{message.text}")
                await message.answer("✅ Твой ответ отправлен анониму!")
            except: await message.answer("❌ Не удалось отправить ответ (юзер заблокировал бота).")
        else:
            await message.answer("❌ Ошибка: я не нашел, кому отвечать (возможно, сообщение слишком старое).")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    

