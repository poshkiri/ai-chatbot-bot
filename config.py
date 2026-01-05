from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str
    BOT_USERNAME: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_bot.db"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "ai_chatbot_bot"
    REDIS_URL: str = ""  # Опционально - для кэширования (оставьте пустым, если не используете)
    # Для Render Redis: rediss://default:password@your-redis.render.com:6379
    # Для локального: redis://localhost:6379/0
    
    # AI Services
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 2000
    
    # Google AI
    GOOGLE_AI_API_KEY: str = ""
    GOOGLE_AI_MODEL: str = "gemini-pro"  # Используем стабильную модель
    GOOGLE_AI_TEMPERATURE: float = 0.7
    
    # Выбор провайдера: "openai" или "google"
    AI_PROVIDER: str = "openai"
    
    # AI Optimization
    AI_CACHE_ENABLED: bool = True  # Кэширование запросов
    AI_CACHE_TTL: int = 3600  # TTL кэша в секундах (1 час)
    AI_TIMEOUT: int = 30  # Таймаут запроса к AI API (секунды)
    AI_MAX_RETRIES: int = 3  # Максимум повторных попыток
    AI_RETRY_DELAY: int = 2  # Задержка между попытками (секунды)
    
    # Fallback settings
    AI_FALLBACK_ENABLED: bool = True  # Использовать fallback модель
    AI_FALLBACK_MODEL: str = "gpt-3.5-turbo"  # Fallback модель (для OpenAI)
    
    # Channel Subscription
    REQUIRED_CHANNEL_ID: str = ""  # @channel_username или channel_id
    REQUIRED_CHANNEL_USERNAME: str = ""  # Без @
    CHANNEL_CHECK_CACHE_TTL: int = 300  # Кэш проверки подписки (5 минут)
    
    # Payments
    PAYMENT_PROVIDER_TOKEN: str = ""
    
    # Subscription Settings
    FREE_MESSAGES_LIMIT: int = 10  # Количество бесплатных сообщений
    TRIAL_MESSAGES_LIMIT: int = 50  # Лимит сообщений в пробный период
    TRIAL_DURATION_DAYS: int = 7  # Длительность пробного периода
    SUBSCRIPTION_PRICE: int = 999  # Цена подписки в центах ($9.99)
    SUBSCRIPTION_DURATION_DAYS: int = 30
    
    # Rate Limiting (оптимизированные лимиты)
    # Free tier
    RATE_LIMIT_FREE_PER_MINUTE: int = 5
    RATE_LIMIT_FREE_PER_HOUR: int = 50
    RATE_LIMIT_FREE_PER_DAY: int = 200
    
    # Paid tier
    RATE_LIMIT_PAID_PER_MINUTE: int = 20
    RATE_LIMIT_PAID_PER_HOUR: int = 500
    RATE_LIMIT_PAID_PER_DAY: int = 5000
    
    # Admin
    ADMIN_USER_IDS: str = ""
    
    # Broadcast
    BROADCAST_BATCH_SIZE: int = 30
    BROADCAST_DELAY: float = 0.05  # Задержка между сообщениями (секунды)
    
    # Media Processing
    MAX_IMAGE_SIZE_MB: int = 10  # Максимальный размер изображения
    MAX_AUDIO_SIZE_MB: int = 20  # Максимальный размер аудио
    MEDIA_PROCESSING_TIMEOUT: int = 60  # Таймаут обработки медиа
    
    # History & Storage Optimization
    MAX_CONVERSATION_LENGTH: int = 100  # Максимум сообщений в диалоге
    HISTORY_COMPRESSION_ENABLED: bool = True  # Сжатие старых диалогов
    ARCHIVE_OLD_CONVERSATIONS_DAYS: int = 90  # Архивация диалогов старше 90 дней
    
    # Monitoring & Analytics
    ANALYTICS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""  # Для мониторинга ошибок (опционально)
    
    # Performance
    ENABLE_TYPING_ACTION: bool = True  # Показывать "печатает..."
    TYPING_ACTION_DURATION: int = 5  # Обновлять статус каждые N секунд
    ASYNC_TASKS_ENABLED: bool = True  # Асинхронная обработка длительных задач
    
    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_USER_IDS:
            return []
        return [int(uid.strip()) for uid in self.ADMIN_USER_IDS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

