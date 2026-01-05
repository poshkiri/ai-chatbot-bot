import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from database.connection import engine, init_mongodb, close_mongodb
from database.models import Base
from handlers import commands, callbacks, messages, payments, admin
from middleware.database import DatabaseMiddleware
from middleware.error_handler import ErrorHandlerMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.subscription import SubscriptionCheckMiddleware
from database.redis_client import get_redis_client

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_tables():
    """Создание таблиц в БД"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    """Главная функция"""
    # Инициализация MongoDB
    if init_mongodb():
        logger.info("✅ MongoDB подключена")
    else:
        logger.warning("⚠️  MongoDB недоступна, используется SQLite")
    
    # Инициализация бота
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Инициализация диспетчера
    # Проверяем доступность Redis (опционально)
    storage = MemoryStorage()  # По умолчанию используем MemoryStorage
    
    redis_client = await get_redis_client()
    if redis_client:
        try:
            await redis_client.ping()
            # Настраиваем RedisStorage с поддержкой SSL для облачных сервисов
            if settings.REDIS_URL.startswith("rediss://") or "render.com" in settings.REDIS_URL:
                redis_url_for_storage = settings.REDIS_URL.replace("rediss://", "redis://")
                storage = RedisStorage.from_url(redis_url_for_storage, ssl=True)
            else:
                storage = RedisStorage.from_url(settings.REDIS_URL)
            logger.info("✅ Redis подключен, используется RedisStorage")
        except Exception as e:
            logger.warning(f"⚠️  Redis недоступен ({e}), используется MemoryStorage")
            storage = MemoryStorage()
    else:
        logger.info("ℹ️  Redis не настроен, используется MemoryStorage")
    
    dp = Dispatcher(storage=storage)
    
    # Регистрация middleware (важен порядок!)
    # 1. Error handler - первый, чтобы перехватывать все ошибки
    error_handler = ErrorHandlerMiddleware()
    dp.message.middleware(error_handler)
    dp.callback_query.middleware(error_handler)
    
    # 2. Database - для инъекции сессии БД
    database_middleware = DatabaseMiddleware()
    dp.message.middleware(database_middleware)
    dp.callback_query.middleware(database_middleware)
    
    # 3. Rate limit - проверка лимитов
    rate_limit_middleware = RateLimitMiddleware()
    dp.message.middleware(rate_limit_middleware)
    dp.callback_query.middleware(rate_limit_middleware)
    
    # 4. Subscription check - проверка подписки на канал
    subscription_middleware = SubscriptionCheckMiddleware()
    dp.message.middleware(subscription_middleware)
    dp.callback_query.middleware(subscription_middleware)
    
    # Регистрация роутеров (важен порядок!)
    # 1. Payments - должен быть первым для перехвата платежей
    dp.include_router(payments.router)
    
    # 2. Commands - команды бота
    dp.include_router(commands.router)
    
    # 3. Callbacks - обработка кнопок
    dp.include_router(callbacks.router)
    
    # 4. Admin - админ-функции
    dp.include_router(admin.router)
    
    # 5. Messages - обработка сообщений (должен быть последним)
    dp.include_router(messages.router)
    
    # Проверка подключения к Telegram API
    try:
        logger.info("Проверка подключения к Telegram API...")
        me = await bot.get_me()
        logger.info(f"✅ Бот подключен: @{me.username} (ID: {me.id})")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Telegram API: {e}")
        logger.error("Возможные причины:")
        logger.error("1. Проблемы с интернет-соединением")
        logger.error("2. Неправильный BOT_TOKEN")
        logger.error("3. Telegram API временно недоступен")
        await bot.session.close()
        return
    
    # Создание таблиц
    try:
        await create_tables()
        logger.info("✅ Таблицы созданы")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        logger.warning("Продолжаем работу, но возможны проблемы с БД")
    
    # Запуск бота
    logger.info("🚀 Бот запущен и готов к работе!")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при работе бота: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    finally:
        # Закрываем подключение к MongoDB
        try:
            asyncio.run(close_mongodb())
        except Exception as e:
            logger.warning(f"Ошибка при закрытии MongoDB: {e}")

