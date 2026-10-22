import asyncio
import json
import logging
import os
from urllib.parse import quote
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# === НАЛАШТУВАННЯ ===
BOT_TOKEN = "ВАШ_ТЕЛЕГРАМ_БОТ_ТОКЕН"
ADMIN_ID = 123456789  # Ваш особистий Telegram ID
WEB_APP_URL = "https://your-domain.com/index.html"  # Посилання на ваш розміщений index.html
MONOBANK_LINK = "https://send.monobank.ua/jar/3NdgaE1Lzq"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Accounts and Firebase are intentionally not used; loyalty cards are updated manually.

# Temporary chat list for broadcasts only; loyalty balances are handled manually.
subscribers = set()

# --- ОБРОБКА /start ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    subscribers.add(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎴 Скретч-картка та запис", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text="💬 Зв'язок з адміністраторкою", url="https://t.me/AnHrok")]
    ])
    await message.answer(
        "Привіт! Вітаємо у партнерській програмі розсилок ANEI ENGLISH.\n\n"
        "Відкрийте скретч-картку, оберіть розсилку й тему та надішліть заявку. "
        "Після оплати адміністраторка вручну оновить картку й надішле її вам у директ.",
        reply_markup=kb
    )

# --- SIMPLE BOOKING: NO LOGIN OR ACCOUNT REQUIRED ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
    except (ValueError, TypeError):
        await message.answer("Не вдалося прочитати заявку. Спробуйте ще раз.")
        return

    if data.get("action") != "booking":
        await message.answer("Не вдалося обробити заявку. Оновіть форму й спробуйте ще раз.")
        return

    channel = str(data.get("channel", "")).strip()
    bundle = str(data.get("bundle", "")).strip()
    topic = str(data.get("topic", "")).strip()
    if not channel or not bundle or not topic:
        await message.answer("Будь ласка, заповніть канал, розсилку й тему.")
        return

    user_info = "@" + message.from_user.username if message.from_user.username else message.from_user.full_name
    admin_msg = (
        "НОВА ЗАЯВКА НА РОЗСИЛКУ\n\n"
        f"Telegram: {user_info} (ID: {message.from_user.id})\n"
        f"Канал: {channel}\nРозсилка: {bundle}\nТема: {topic}\n"
        "Статус: очікує оплати та підтвердження"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_msg)
    except Exception:
        logging.exception("Could not send booking to admin")
        await message.answer("Не вдалося надіслати заявку адміністраторці. Напишіть @AnHrok.")
        return

    payment_comment = quote(f"{channel} | {bundle} | {topic}")
    payment_url = f"{MONOBANK_LINK}?text={payment_comment}"
    payment_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти до оплати", url=payment_url)],
        [InlineKeyboardButton(text="Написати адміністраторці", url="https://t.me/AnHrok")]
    ])
    await message.answer(
        "Заявку надіслано адміністраторці!\n\n"
        f"Канал: {channel}\nРозсилка: {bundle}\nТема: {topic}\n\n"
        "Оплатіть участь за посиланням нижче. Після перевірки я вручну оновлю вашу скретч-картку й надішлю її вам у директ.",
        reply_markup=payment_kb
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
    for uid in subscribers:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Скретч-картка та запис", web_app=WebAppInfo(url=WEB_APP_URL))]
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
