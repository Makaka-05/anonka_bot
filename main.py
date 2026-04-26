import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- НАСТРОЙКИ ---
TOKEN = "8720756817:AAH9gtMpM8K1RlEVUZVcw_ulnWrMPDsYY70"
# Добавь сюда свой ID и ID друга через запятую
ADMIN_IDS = [5275461907, 7919798306] 

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def setup_db():
    conn = sqlite3.connect("anonymous_pro.db")
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    conn.close()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    setup_db()
    user_id = message.from_user.id
    name = message.from_user.full_name
    
    # Сохраняем пользователя
    conn = sqlite3.connect("anonymous_pro.db")
    conn.execute("INSERT OR REPLACE INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()

    args = message.text.split()
    if len(args) > 1:
        target_id = args[1]
        return await message.answer(
            f"👤 Напиши анонимное сообщение для ID <code>{target_id}</code>:",
            reply_markup=InlineKeyboardBuilder().button(text="❌ Отмена", callback_data="cancel").as_markup()
        )

    # Главное меню как на скрине
    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    text = (
        "<b>Начните получать анонимные вопросы прямо сейчас!</b>\n\n"
        f"👉 <code>{link}</code>\n\n"
        "Разместите эту ссылку в описании своего профиля!"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Поделиться ссылкой", url=f"https://t.me/share/url?url={link}")
    kb.button(text="👥 Добавить бота в чат", url=f"https://t.me/{(await bot.get_me()).username}?startgroup=true")
    kb.adjust(1)
    
    await message.answer(text, reply_markup=kb.as_markup())

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_message(message: types.Message):
    # Если это ответ на сообщение с ID (анонимка)
    if message.reply_to_message and "ID" in message.reply_to_message.text:
        try:
            # Извлекаем ID получателя из текста сообщения, на которое отвечаем
            target_id = int(message.reply_to_message.text.split("ID")[1].split(":")[0].strip())
            
            # 1. Отправляем получателю
            await bot.send_message(target_id, f"<b>📩 Новое анонимное сообщение:</b>\n\n{message.text}")
            await message.answer("✅ Сообщение успешно отправлено.")

            # 2. ЛОГИ ДЛЯ АДМИНОВ (Кликабельные юзеры)
            sender = message.from_user
            log_text = (
                f"🛰 <b>ЛОГ ПЕРЕСЫЛКИ:</b>\n"
                f"👤 От: <a href='tg://user?id={sender.id}'>{sender.full_name}</a> (<code>{sender.id}</code>)\n"
                f"🎯 Кому: <a href='tg://user?id={target_id}'>Получатель</a> (<code>{target_id}</code>)\n"
                f"📝 Текст: {message.text}"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, log_text)
                except:
                    pass
        except Exception as e:
            await message.answer("❌ Ошибка при отправке. Возможно, пользователь заблокировал бота.")

async def main():
    print("--- БОТ ЗАПУЩЕН (ЛОГИ ВКЛЮЧЕНЫ) ---")
    setup_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
