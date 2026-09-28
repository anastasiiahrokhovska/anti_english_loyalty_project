# ANEI ENGLISH — Loyalty Card Bot & WebApp

Цей проєкт містить повністю готовий код Telegram WebApp з інтерфейсом картки лояльності та бота на Python (`aiogram 3`).

## Структура проекту:
- `index.html` — Веб-сторінка картки (Web App) для Telegram.
- `bot.py` — Телеграм-бот для обробки бронювань, видачі штампів та масових розсилок.
- `requirements.txt` — Список потрібних Python-бібліотек.

## Як запустити у PyCharm:
1. Розархівуйте ZIP-файл та відкрийте папку через **PyCharm**.
2. Встановіть залежності у терміналі PyCharm:
   ```bash
   pip install -r requirements.txt
   ```
3. Відкрийте `bot.py` і вкажіть свої дані:
   - `BOT_TOKEN` — Токен бота від @BotFather
   - `ADMIN_ID` — Ваш Telegram ID (можна дізнатися через @userinfobot)
   - `WEB_APP_URL` — Посилання на розгорнутий `index.html` (наприклад, з GitHub Pages).
4. Запустіть файл `bot.py`.
