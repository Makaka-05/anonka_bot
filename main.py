import asyncio
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]
GROUP_ID = -1003784828350  # <--- ВСТАВЬ СЮДА ID СВОЕЙ ГРУППЫ

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

def get_keyboard():
    kb = [
        [KeyboardButton(text="✉️ Личный вопрос"), KeyboardButton(text="📢 В группу")],
        [KeyboardButton(text="📊 Статистика")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("👋 Выбери, куда хочешь отправить анонимку:", reply_markup=get_keyboard())

@dp.message(F.text == "✉️ Личный вопрос")
async def personal_choice(message: types.Message):
    await message.answer("✍️ Напиши вопрос для админа, и я передам его лично!")

@dp.message(F.text == "📢 В группу")
async def group_choice(message: types.Message):
    await message.answer("✍️ Напиши вопрос, и я опубликую его в группе анонимно!")

@dp.message(F.text)
async def handle_message(message: types.Message):
    # Пытаемся понять, куда отправить сообщение (последний выбор пользователя)
    # Используем состояние (упрощенно через имя бота или просто логику)
    
    # 1. Если пользователь хочет отправить в группу
    if message.reply_to_message and "опубликую его в группе" in message.reply_to_message.text:
        await bot.send_message(GROUP_ID, f"📥 <b>Анонимно в группу:</b>\n\n{message.text}")
        await message.answer("✅ Опубликовано в группе!")
        await notify_admins(message, "ГРУППА")
        
    # 2. Если пользователь хочет отправить лично админу
    elif message.reply_to_message and "передам его лично" in message.reply_to_message.text:
        for admin in ADMIN_IDS:
            await bot.send_message(admin, f"📥 <b>Личный вопрос:</b>\n\n{message.text}")
        await message.answer("✅ Отправлено лично админу!")
        await notify_admins(message, "ЛИЧНО")
    
    else:
        await message.answer("⚠️ Нажми на кнопку меню и выбери формат, затем 'Ответить' на сообщение бота!")

async def notify_admins(message, mode):
    u = message.from_user
    log = f"🕵️ <b>АВТОР:</b> {u.full_name} (@{u.username})\n🆔 <code>{u.id}</code>\n🎯 <b>КУДА:</b> {mode}\n📝 <b>ТЕКСТ:</b> {message.text}"
    for admin in ADMIN_IDS:
        try: await bot.send_message(admin, log)
        except: pass

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
