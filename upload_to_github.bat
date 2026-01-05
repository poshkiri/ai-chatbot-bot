@echo off
echo ====================================
echo Загрузка кода в GitHub
echo ====================================
echo.

REM Проверка наличия Git
git --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Git не установлен!
    echo Установите Git с https://git-scm.com/
    pause
    exit /b 1
)

echo [1/5] Инициализация Git...
if not exist .git (
    git init
    echo Git инициализирован
) else (
    echo Git уже инициализирован
)

echo.
echo [2/5] Добавление файлов...
git add .
echo Файлы добавлены

echo.
echo [3/5] Создание коммита...
git commit -m "Initial commit: AI Telegram Bot"
if errorlevel 1 (
    echo ВНИМАНИЕ: Возможно, нет изменений для коммита
)

echo.
echo [4/5] Настройка удаленного репозитория...
echo.
echo ВАЖНО: Сначала создайте репозиторий на GitHub!
echo 1. Зайдите на https://github.com
echo 2. Создайте новый репозиторий (например: ai-chatbot-bot)
echo 3. НЕ добавляйте README, .gitignore или лицензию
echo.
set /p GITHUB_URL="Введите URL вашего репозитория (например: https://github.com/username/ai-chatbot-bot.git): "

if "%GITHUB_URL%"=="" (
    echo ОШИБКА: URL не введен!
    pause
    exit /b 1
)

git remote remove origin 2>nul
git remote add origin %GITHUB_URL%
echo Удаленный репозиторий добавлен

echo.
echo [5/5] Загрузка на GitHub...
echo.
echo ВНИМАНИЕ: Если GitHub попросит авторизацию:
echo - Используйте Personal Access Token (не пароль)
echo - Создайте токен: GitHub -^> Settings -^> Developer settings -^> Personal access tokens
echo.
git branch -M main
git push -u origin main

if errorlevel 1 (
    echo.
    echo ОШИБКА при загрузке!
    echo Возможные причины:
    echo 1. Неправильный URL репозитория
    echo 2. Репозиторий не создан на GitHub
    echo 3. Проблемы с авторизацией
    pause
    exit /b 1
)

echo.
echo ====================================
echo УСПЕШНО! Код загружен в GitHub!
echo ====================================
echo.
echo Следующий шаг: Деплой на Render
echo Смотрите инструкцию в DEPLOY_GUIDE.md
echo.
pause

