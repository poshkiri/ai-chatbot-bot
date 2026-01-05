"""
Оптимизированный rate limiter с дифференцированными лимитами
"""
import logging
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.models import User, SubscriptionStatus
from database.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter с поддержкой разных лимитов для разных типов пользователей"""
    
    async def check_rate_limit(
        self,
        user_id: int,
        session: AsyncSession,
        operation_type: str = "message"
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверяет rate limit для пользователя
        
        Returns:
            (allowed: bool, error_message: Optional[str])
        """
        try:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return False, "Пользователь не найден"
            
            # Определяем лимиты в зависимости от статуса подписки
            is_paid = (
                user.subscription_status == SubscriptionStatus.ACTIVE
                and user.subscription_expires_at
                and user.subscription_expires_at > datetime.utcnow()
            )
            
            if is_paid:
                per_minute = settings.RATE_LIMIT_PAID_PER_MINUTE
                per_hour = settings.RATE_LIMIT_PAID_PER_HOUR
                per_day = settings.RATE_LIMIT_PAID_PER_DAY
            else:
                per_minute = settings.RATE_LIMIT_FREE_PER_MINUTE
                per_hour = settings.RATE_LIMIT_FREE_PER_HOUR
                per_day = settings.RATE_LIMIT_FREE_PER_DAY
            
            # Пробуем использовать Redis, если доступен
            redis_client = await get_redis_client()
            
            if redis_client:
                # Используем Redis для rate limiting (быстрее)
                try:
                    now = datetime.utcnow()
                    minute_key = f"rate_limit:{user_id}:minute:{now.strftime('%Y%m%d%H%M')}"
                    hour_key = f"rate_limit:{user_id}:hour:{now.strftime('%Y%m%d%H')}"
                    day_key = f"rate_limit:{user_id}:day:{now.strftime('%Y%m%d')}"
                    
                    # Проверяем лимиты
                    minute_count = await redis_client.get(minute_key)
                    if minute_count and int(minute_count) >= per_minute:
                        return False, f"Превышен лимит: {per_minute} запросов в минуту"
                    
                    hour_count = await redis_client.get(hour_key)
                    if hour_count and int(hour_count) >= per_hour:
                        return False, f"Превышен лимит: {per_hour} запросов в час"
                    
                    day_count = await redis_client.get(day_key)
                    if day_count and int(day_count) >= per_day:
                        return False, f"Превышен лимит: {per_day} запросов в день"
                    
                    # Увеличиваем счетчики
                    pipe = redis_client.pipeline()
                    pipe.incr(minute_key)
                    pipe.expire(minute_key, 60)
                    pipe.incr(hour_key)
                    pipe.expire(hour_key, 3600)
                    pipe.incr(day_key)
                    pipe.expire(day_key, 86400)
                    await pipe.execute()
                    
                    return True, None
                except Exception as redis_error:
                    logger.warning(f"Ошибка Redis при rate limiting: {redis_error}, используем упрощенную проверку")
            
            # Упрощенная проверка без Redis (через БД)
            # Для простоты разрешаем все запросы, если Redis недоступен
            # В продакшене можно добавить проверку через таблицу в БД
            return True, None
            
        except Exception as e:
            logger.error(f"Ошибка при проверке rate limit: {e}")
            # При ошибке разрешаем запрос (fail-open для доступности)
            return True, None
    
    async def get_rate_limit_info(
        self,
        user_id: int,
        session: AsyncSession
    ) -> dict:
        """Возвращает информацию о текущих лимитах пользователя"""
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {}
        
        is_paid = (
            user.subscription_status == SubscriptionStatus.ACTIVE
            and user.subscription_expires_at
            and user.subscription_expires_at > datetime.utcnow()
        )
        
        if is_paid:
            return {
                "per_minute": settings.RATE_LIMIT_PAID_PER_MINUTE,
                "per_hour": settings.RATE_LIMIT_PAID_PER_HOUR,
                "per_day": settings.RATE_LIMIT_PAID_PER_DAY,
                "is_paid": True
            }
        else:
            return {
                "per_minute": settings.RATE_LIMIT_FREE_PER_MINUTE,
                "per_hour": settings.RATE_LIMIT_FREE_PER_HOUR,
                "per_day": settings.RATE_LIMIT_FREE_PER_DAY,
                "is_paid": False
            }


rate_limiter = RateLimiter()

