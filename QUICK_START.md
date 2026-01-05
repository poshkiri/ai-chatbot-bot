# ⚡ Быстрый старт

## 🚀 Загрузка в GitHub (3 шага)

### 1. Создайте репозиторий на GitHub
- Зайдите на [github.com](https://github.com)
- Нажмите **"+"** → **"New repository"**
- Имя: `ai-chatbot-bot`
- **НЕ** ставьте галочки на README, .gitignore, license
- Нажмите **"Create repository"**

### 2. Запустите скрипт (Windows)
Дважды кликните на `upload_to_github.bat` и следуйте инструкциям

### 3. Или выполните команды вручную:

```bash
cd ai-chatbot-bot
git init
git add .
git commit -m "Initial commit: AI Telegram Bot"
git branch -M main
git remote add origin https://github.com/ВАШ_USERNAME/ai-chatbot-bot.git
git push -u origin main
```

**Если нужна авторизация:**
- Используйте **Personal Access Token** (не пароль)
- Создайте: GitHub → Settings → Developer settings → Personal access tokens

---

## 🌐 Деплой на Render (5 шагов)

### 1. Создайте PostgreSQL базу
- Render Dashboard → **"New +"** → **"PostgreSQL"**
- Name: `ai-chatbot-db`
- Plan: `Free`
- Скопируйте **Internal Database URL**

### 2. Создайте Web Service
- Render Dashboard → **"New +"** → **"Web Service"**
- Подключите GitHub репозиторий `ai-chatbot-bot`

### 3. Настройки сервиса:
```
Build Command: pip install -r requirements.txt
Start Command: python main.py
```

### 4. Добавьте переменные окружения:
```
BOT_TOKEN=ваш_токен_от_BotFather
GOOGLE_AI_API_KEY=ваш_google_ai_ключ
AI_PROVIDER=google
DATABASE_URL=вставьте_Internal_Database_URL
ADMIN_USER_IDS=ваш_telegram_id
```

### 5. Запустите деплой
- Нажмите **"Create Web Service"**
- Ждите 2-5 минут
- Проверьте логи

---

## ✅ Проверка работы

1. Откройте логи в Render
2. Должно быть: `✅ Бот запущен и готов к работе!`
3. Найдите бота в Telegram
4. Отправьте `/start`
5. Бот должен ответить! 🎉

---

## 📚 Подробная инструкция

Смотрите `DEPLOY_GUIDE.md` для детальной инструкции

---

## ❓ Проблемы?

### Ошибка авторизации GitHub
- Используйте Personal Access Token вместо пароля

### Ошибка подключения к БД
- Используйте **Internal Database URL** (не External!)

### Бот не запускается
- Проверьте все переменные окружения
- Проверьте логи в Render

