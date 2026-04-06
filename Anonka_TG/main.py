import asyncio
from aiogram import Bot, Dispatcher, types

TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_ID = 7919798306   # твой ID
TARGET_ID = 7919798306  # ID друга

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message()
async def handle_message(message: types.Message):
    user = message.from_user

    # 👑 тебе (админу)
    await bot.send_message(
        ADMIN_ID,
        f"📨 Новое сообщение\n"
        f"👤 @{user.username}\n"
        f"🆔 {user.id}\n"
        f"💬 {message.text}"
    )

    # 💌 другу (анонимка)
    await bot.send_message(
        TARGET_ID,
        f"💌 Анонимное сообщение:\n{message.text}"
    )

    await message.answer("✅ Отправлено!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())