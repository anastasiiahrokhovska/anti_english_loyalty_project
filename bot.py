import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# === НАЛАШТУВАННЯ ===
BOT_TOKEN = "ВАШ_ТЕЛЕГРАМ_БОТ_ТОКЕН"
ADMIN_ID = 123456789  # Ваш особистий Telegram ID
WEB_APP_URL = "https://your-domain.com/index.html"  # Посилання на ваш розміщений index.html

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# База даних у пам'яті (структура: { user_id: {"stamps": int, "username": str} })
users_db = {}

# --- ОБРОБКА /start ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    if user_id not in users_db:
        users_db[user_id] = {"stamps": 0, "username": username}

    stamps = users_db[user_id]["stamps"]
    user_webapp_url = f"{WEB_APP_URL}?stamps={stamps}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎴 Моя Скетч-Картка", web_app=WebAppInfo(url=user_webapp_url))],
        [InlineKeyboardButton(text="💬 Зв'язок з Адміном", url="https://t.me/AnHrok")]
    ])

    await message.answer(
        f"Привіт, {username}! 👋\n\n"
        f"Вітаємо у партнерській програмі розсилок **ANEI ENGLISH**.\n"
        f"Ваш поточний баланс: **{stamps}/7** штампів.\n\n"
        f"Натисніть кнопку нижче, щоб відкрити картку лояльності та забронювати слот!",
        reply_markup=kb,
        parse_mode="Markdown"
    )

# --- ОБРОБКА ДАНИХ З WEB APP ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    user_id = message.from_user.id
    data = json.loads(message.web_app_data.data)

    if data.get("action") == "book_slot":
        topic = data.get("topic")
        date = data.get("date")
        is_free = data.get("isFree")

        user_info = users_db.get(user_id, {"stamps": 0, "username": message.from_user.first_name})
        status_text = "🎁 **БЕЗКОШТОВНА 8-ма розсилка!**" if is_free else "💳 Потрібна оплата"

        admin_msg = (
            f"📥 **НОВЕ БРОНЮВАННЯ СОТА!**\n\n"
            f"👤 Вчитель: @{user_info['username']} (ID: `{user_id}`)\n"
            f"📌 Тема: {topic}\n"
            f"📅 Дата: {date}\n"
            f"Статус: {status_text}\n"
            f"Поточні штампи: {user_info['stamps']}/7"
        )
        
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Підтвердити +1 Штамп", callback_data=f"add_stamp_{user_id}")],
            [InlineKeyboardButton(text="🔄 Використано (Скинути до 0)", callback_data=f"reset_stamp_{user_id}")]
        ])

        await bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_kb, parse_mode="Markdown")

        await message.answer(
            f"Дякуємо! Ваша заявка на тему: *\"{topic}\"* прийнята.\n"
            f"Адміністратор перевірить дані та підтвердить слот найближчим часом.",
            parse_mode="Markdown"
        )

# --- АДМІН-КЕРУВАННЯ ШТАМПАМИ ---
@dp.callback_query(F.data.startswith("add_stamp_"))
async def add_stamp_handler(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    if user_id in users_db:
        users_db[user_id]["stamps"] += 1
        current_stamps = users_db[user_id]["stamps"]
        
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ **Штамп успішно додано! Баланс: {current_stamps}**",
            parse_mode="Markdown"
        )
        await bot.send_message(
            user_id, 
            f"🎉 Вам зараховано новий штамп! Поточний баланс: **{current_stamps}/7**."
        )

@dp.callback_query(F.data.startswith("reset_stamp_"))
async def reset_stamp_handler(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    if user_id in users_db:
        users_db[user_id]["stamps"] = 0
        
        await callback.message.edit_text(
            f"{callback.message.text}\n\n🔄 **Картку обнулено після безкоштовної розсилки!**",
            parse_mode="Markdown"
        )
        await bot.send_message(
            user_id, 
            "✨ Ви використали свою 8-му безкоштовну розсилку! Вашу картку обнулено, починаємо новий відлік."
        )

# --- АДМІНСЬКА МАСОВА РОЗСИЛКА ---
@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    text_to_send = message.text.replace("/broadcast", "").strip()
    if not text_to_send:
        await message.answer("Введіть текст розсилки після команди. Наприклад:\n`/broadcast Відкрито запис на нову розсилку!`")
        return

    count = 0
    for uid in users_db.keys():
        try:
            user_stamps = users_db[uid]["stamps"]
            user_webapp_url = f"{WEB_APP_URL}?stamps={user_stamps}"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎴 Забронювати слот", web_app=WebAppInfo(url=user_webapp_url))]
            ])
            await bot.send_message(uid, text_to_send, reply_markup=kb)
            count += 1
        except Exception:
            pass

    await message.answer(f"📢 Розсилку успішно надіслано **{count}** користувачам!")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
