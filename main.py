import asyncio
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties

# --- НАСТРОЙКИ ---
TOKEN = "8720756817:AAFFksi2_kKScmLW1XVREa1WUtbcImAyeHE"
ADMIN_IDS = [7919798306, 5275461907]

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("anonymous.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_links 
        (group_id INTEGER PRIMARY KEY, group_name TEXT)
    """)
    conn.commit()
    conn.close()

# --- КЛАВИАТУРА (Исправленная) ---
def get_main_kb():
    # Создаем кнопки именно с теми названиями, которые мы потом проверяем в коде
    kb = [
        [KeyboardButton(text="👤 Моя личная ссылка")],
        [KeyboardButton(text="➕ Подключить группу")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(CommandStart())
async def start(message: types.Message):
    init_db()
    args = message.text.split()
    
    # 1. Если переход по ссылке группы (?start=-100...)
    if len(args) > 1 and args[1].startswith("-100"):
        group_id = args[1]
        await message.answer(
            f"🤫 <b>Анонимка в группу</b>\n\nНапиши сообщение (нажми 'Ответить'), и я отправлю его в чат!\n\n"
            f"🆔 Группы: <code>{group_id}</code>",
            reply_markup=get_main_kb() # Добавляем кнопки, чтобы не пропадали
        )
    
    # 2. Личная анонимка (?start=12345)
    elif len(args) > 1 and args[1].isdigit():
        await message.answer(
            f"🤫 Пиши анонимно для ID <code>{args[1]}</code>\n\n(Нажми 'Ответить')",
            reply_markup=get_main_kb()
        )
    
    # 3. Просто старт
    else:
        await message.answer("Привет! Я бот анонимных сообщений. Выбери действие:", reply_markup=get_main_kb())

# --- ОБРАБОТКА КНОПОК ---

@dp.message(F.text == "👤 Моя личная ссылка")
async def show_personal_link(message: types.Message):
    me = await bot.get_me()
    # Генерируем ссылку на основе ID того, кто нажал на кнопку
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"Твоя личная ссылка (для вопросов лично тебе):\n<code>{link}</code>")

@dp.message(F.text == "➕ Подключить группу")
async def connect_group(message: types.Message):
    await message.answer(
        "Чтобы подключить свою группу:\n\n"
        "1. Добавь меня в свою группу.\n"
        "2. Сделай меня <b>администратором</b>.\n"
        "3. Напиши в группе команду: <code>/setup</code>"
    )

# Команда для активации группы (в группе)
@dp.message(F.text == "/setup")
async def setup_in_group(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        init_db()
        conn = sqlite3.connect("anonymous.db")
        conn.execute("INSERT OR IGNORE INTO group_links VALUES (?, ?)", (message.chat.id, message.chat.title))
        conn.commit()
        conn.close()
        
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start={message.chat.id}"
        await message.answer(f"✅ Группа подключена!\n\nЗакрепите эту ссылку:\n<code>{link}</code>")

# --- ОБРАБОТКА ТЕКСТА ---
@dp.message(F.text)
async def handle_msg(message: types.Message):
    if not message.reply_to_message: return

    # Если ответ на сообщение про группу
    if "Анонимка в группу" in message.reply_to_message.text:
        try:
            target_group = re.findall(r'-100\d+', message.reply_to_message.text)[0]
            await bot.send_message(target_group, f"📥 <b>Новое анонимное сообщение:</b>\n\n{message.text}")
            await message.answer("✅ Отправлено в группу!")
            await notify_admins(message, f"ГРУППА {target_group}")
        except:
            await message.answer("❌ Ошибка. Бот должен быть админом в той группе!")

    # Если личный вопрос
    elif "Пиши анонимно для ID" in message.reply_to_message.text:
        try:
            target_id = re.findall(r'\d+', message.reply_to_message.text)[0]
            await bot.send_message(target_id, f"📥 <b>Личный вопрос:</b>\n\n{message.text}")
            await message.answer("✅ Доставлено!")
            await notify_admins(message, f"ЛИЧНО {target_id}")
        except:
            await message.answer("❌ Ошибка доставки.")

async def notify_admins(message, mode):
    u = message.from_user
    # Создаем красивую ссылку на имя
    user_link = f"<a href='tg://user?id={u.id}'>{u.full_name}</a>"
    
    # Добавляем юзернейм, если он есть (будет подсвечиваться синим)
    username = f" (@{u.username})" if u.username else ""
    
    # Формируем лог
    log = (
        f"🕵️ <b>НОВЫЙ ЛОГ</b>\n\n"
        f"👤 <b>От:</b> {user_link}{username}\n"
        f"🆔 <b>ID:</b> <code>{u.id}</code>\n"
        f"🎯 <b>Куда:</b> {mode}\n"
        f"📝 <b>Текст:</b> {message.text}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, log)
        except Exception as e:
            print(f"Ошибка логирования для {admin_id}: {e}")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
