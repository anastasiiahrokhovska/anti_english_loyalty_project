import asyncio
import json
import logging
import os
import hashlib
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, db as firebase_db

# === НАЛАШТУВАННЯ ===
BOT_TOKEN = "ВАШ_ТЕЛЕГРАМ_БОТ_ТОКЕН"
ADMIN_ID = 123456789  # Ваш особистий Telegram ID
WEB_APP_URL = "https://your-domain.com/index.html"  # Посилання на ваш розміщений index.html
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://aneienglishloyaltyproject-default-rtdb.europe-west1.firebasedatabase.app")
FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

if FIREBASE_SERVICE_ACCOUNT_JSON and not firebase_admin._apps:
    firebase_credential = credentials.Certificate(json.loads(FIREBASE_SERVICE_ACCOUNT_JSON))
    firebase_admin.initialize_app(firebase_credential, {"databaseURL": FIREBASE_DATABASE_URL})

def firebase_ready():
    return bool(FIREBASE_SERVICE_ACCOUNT_JSON and firebase_admin._apps)


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
    try:
        data = json.loads(message.web_app_data.data)
    except (ValueError, TypeError):
        await message.answer("Не вдалося прочитати заявку. Спробуйте ще раз.")
        return

    if data.get("action") != "booking":
        await message.answer("Ця дія більше не підтримується. Оновіть WebApp і спробуйте ще раз.")
        return

    if not firebase_ready():
        logging.error("Firebase Admin is not configured")
        await message.answer("Система кабінетів ще налаштовується. Будь ласка, напишіть адміністраторці.")
        return

    channel_uid = str(data.get("channelUid", ""))
    id_token = str(data.get("idToken", ""))
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        if decoded.get("uid") != channel_uid:
            raise ValueError("Firebase UID does not match token")
        profile_ref = firebase_db.reference(f"channel_accounts/{channel_uid}")
        profile = profile_ref.get()
        if not profile or not profile.get("channel"):
            raise ValueError("Channel profile not found")
        channel = str(data.get("channel", "")).strip()
        if channel.lower() != str(profile["channel"]).lower():
            raise ValueError("Channel does not match profile")
    except Exception:
        logging.exception("Channel booking authentication failed")
        await message.answer("Не вдалося підтвердити вхід до кабінету. Увійдіть знову або зверніться до адміністраторки.")
        return

    topic = str(data.get("topic", "")).strip()
    bundle = str(data.get("bundle", "")).strip()
    if not topic or not bundle:
        await message.answer("Оберіть розсилку та тему перед бронюванням.")
        return

    # Check existing topics and reserve an unused topic under a deterministic key.
    topics_ref = firebase_db.reference("taken_topics")
    existing = topics_ref.get() or {}
    if topic in existing.values():
        await message.answer("На жаль, цю тему вже забронювали. Оновіть список тем і виберіть іншу.")
        return
    topic_key = hashlib.sha256(topic.encode("utf-8")).hexdigest()
    reservation_ref = topics_ref.child(topic_key)
    transaction_result = reservation_ref.transaction(lambda current: topic if current is None else current)
    if transaction_result != topic:
        await message.answer("На жаль, цю тему щойно забронювали. Виберіть іншу.")
        return

    stamps = int(profile.get("stamps", 0))
    is_free = stamps >= 7
    user_info = message.from_user.username or message.from_user.first_name or str(message.from_user.id)
    status_text = "🎁 БЕЗКОШТОВНА 8-ма участь — очікує підтвердження" if is_free else "💳 Очікує оплати"
    admin_msg = (
        "📥 НОВЕ БРОНЮВАННЯ РОЗСИЛКИ!\\n\\n"
        f"👤 Telegram: @{user_info} (ID: {message.from_user.id})\\n"
        f"📣 Розсилка: {bundle}\\n"
        f"📌 Тема: {topic}\\n"
        f"🔗 Канал: {profile['channel']}\\n"
        f"Статус: {status_text}\\n"
        f"Поточні штампи: {stamps}/7"
    )
    if is_free:
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Підтвердити безкоштовну 8-му", callback_data=f"channel_free_{channel_uid}")]
        ])
    else:
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Підтвердити платну участь (+1)", callback_data=f"channel_add_{channel_uid}")]
        ])

    try:
        await bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_kb)
    except Exception:
        logging.exception("Could not send booking to admin")
        reservation_ref.delete()
        await message.answer("Не вдалося надіслати заявку адміністраторці. Спробуйте пізніше.")
        return

    await message.answer(
        f"Заявку на тему «{topic}» для розсилки «{bundle}» надіслано адміністраторці. "
        + ("Ви можете використати бонус 8-ї участі після підтвердження." if is_free else "Після підтвердження оплати вам зарахують штамп.")
    )

# --- ПЕРСОНАЛЬНІ ШТАМПИ КАНАЛІВ (Firebase) ---
@dp.callback_query(F.data.startswith("channel_add_"))
async def add_channel_stamp_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Немає доступу", show_alert=True)
        return
    if not firebase_ready():
        await callback.answer("Firebase не налаштовано", show_alert=True)
        return
    channel_uid = callback.data.removeprefix("channel_add_")
    ref = firebase_db.reference(f"channel_accounts/{channel_uid}")
    profile = ref.get()
    if not profile:
        await callback.answer("Кабінет не знайдено", show_alert=True)
        return
    stamps = int(profile.get("stamps", 0))
    if stamps >= 7:
        await callback.answer("У каналу вже доступний безкоштовний бонус.", show_alert=True)
        return
    stamps += 1
    ref.update({"stamps": stamps, "freeRewardAvailable": stamps >= 7})
    await callback.message.edit_text(
        f"{callback.message.text}\\n\\nШтамп зараховано для {profile.get('channel', channel_uid)}. Баланс: {stamps}/7."
    )
    await callback.answer("Штамп зараховано")

@dp.callback_query(F.data.startswith("channel_free_"))
async def use_channel_free_reward_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Немає доступу", show_alert=True)
        return
    if not firebase_ready():
        await callback.answer("Firebase не налаштовано", show_alert=True)
        return
    channel_uid = callback.data.removeprefix("channel_free_")
    ref = firebase_db.reference(f"channel_accounts/{channel_uid}")
    profile = ref.get()
    if not profile or int(profile.get("stamps", 0)) < 7:
        await callback.answer("Безкоштовна участь ще недоступна.", show_alert=True)
        return
    ref.update({
        "stamps": 0,
        "freeRewardAvailable": False,
        "freeRewardsUsed": int(profile.get("freeRewardsUsed", 0)) + 1
    })
    await callback.message.edit_text(
        f"{callback.message.text}\\n\\nБезкоштовну 8-му участь підтверджено для {profile.get('channel', channel_uid)}. Картку почато заново (0/7)."
    )
    await callback.answer("Бонус використано")

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
