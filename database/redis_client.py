"""
Опциональный Redis клиент
Если Redis недоступен, бот будет работать без него
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Глобальная переменная для Redis клиента
_redis_client = None
_redis_available = False

async def get_redis_client():
    """
    Получить Redis клиент (опционально)
    Возвращает None, если Redis недоступен
    """
    global _redis_client, _redis_available
    
    if _redis_client is not None:
        return _redis_client if _redis_available else None
    
    # Пробуем создать клиент только если URL указан
    from config import settings
    
    if not settings.REDIS_URL or settings.REDIS_URL == "redis://localhost:6379/0":
        # Redis не настроен, пропускаем
        _redis_available = False
        return None
    
    try:
        import redis.asyncio as redis
        
        redis_url = settings.REDIS_URL
        
        # Поддержка SSL для облачных сервисов
        if redis_url.startswith("rediss://") or "render.com" in redis_url or "upstash.io" in redis_url:
            redis_url_parsed = redis_url.replace("rediss://", "redis://") if redis_url.startswith("rediss://") else redis_url
            _redis_client = redis.from_url(
                redis_url_parsed,
                decode_responses=True,
                ssl=True,
                ssl_cert_reqs=None
            )
        else:
            _redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Проверяем подключение
        await _redis_client.ping()
        _redis_available = True
        logger.info("✅ Redis подключен")
        return _redis_client
        
    except Exception as e:
        logger.warning(f"⚠️  Redis недоступен: {e}. Бот будет работать без Redis.")
        _redis_available = False
        _redis_client = None
        return None

# Для обратной совместимости
async def redis_client():
    """Алиас для get_redis_client()"""
    return await get_redis_client()

