import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- ДАННЫЕ (ПРОВЕРЬ ИХ!) ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]

bot = Bot(token=TOKEN, parse_mode="HTML")
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
        await message.answer(f"🤫 Пиши анонимно для пользователя <code>{target}</code>\n\n(Нажми на это сообщение и выбери <b>'Ответить'</b>)")
    else:
        init_db()
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        conn.close()
        await message.answer("Меню активировано!", reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text)
async def handle_all_messages(message: types.Message):
    # 1. СНАЧАЛА ПРОВЕРЯЕМ АНОНИМКУ (самое важное!)
    if message.reply_to_message and "пользователя" in message.reply_to_message.text:
        try:
            target_id = message.reply_to_message.text.split("<code>")[1].split("</code>")[0]
            
            # Отправка получателю
            await bot.send_message(target_id, f"📥 <b>Новый анонимный вопрос:</b>\n\n{message.text}")
            
            # ОТПРАВКА ЛОГА ТЕБЕ (почему ты его не видел)
            u = message.from_user
            u_link = f"<a href='tg://user?id={u.id}'>{u.full_name}</a>"
            un = f" (@{u.username})" if u.username else ""
            
            log_text = (
                f"🕵️ <b>ЛОГ АДМИНА</b>\n"
                f"👤 <b>От:</b> {u_link}{un}\n"
                f"🎯 <b>Кому (ID):</b> <code>{target_id}</code>\n"
                f"📝 <b>Текст:</b> {message.text}"
            )
            
            for admin_id in ADMIN_IDS:
                try: await bot.send_message(admin_id, log_text)
                except: pass
            
            await message.answer("✅ Сообщение доставлено!")
            return # Выходим, чтобы кнопки ниже не срабатывали
        except:
            await message.answer("❌ Ошибка отправки")
            return

    # 2. ПОТОМ ПРОВЕРЯЕМ КНОПКИ
    if message.text == "🔗 Моя ссылка":
        bot_info = await bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
        await message.answer(f"Твоя ссылка:\n<code>{link}</code>")
    
    elif message.text == "📊 Статистика" and message.from_user.id in ADMIN_IDS:
        conn = sqlite3.connect("users.db")
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        await message.answer(f"Всего юзеров: <b>{count}</b>")
    
    else:
        # Если это просто текст без реплая
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("⚠️ Нажми 'Ответить' на сообщение с ID, чтобы отправить анонимку!")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
