"""
Сервис для проверки подписки пользователя на канал
С кэшированием для оптимизации производительности
"""
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.models import User
from database.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class ChannelCheckService:
    """Сервис для проверки подписки на канал с кэшированием"""
    
    async def check_subscription(
        self,
        bot: Bot,
        user_id: int,
        session: AsyncSession,
        force_check: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверяет подписку пользователя на канал
        
        Returns:
            (is_subscribed: bool, error_message: Optional[str])
        """
        if not settings.REQUIRED_CHANNEL_ID:
            # Если канал не указан, считаем что подписка не требуется
            return True, None
        
        try:
            # Проверяем кэш Redis (если доступен)
            redis_client = await get_redis_client()
            if redis_client and not force_check:
                try:
                    cache_key = f"channel_sub:{user_id}"
                    cached = await redis_client.get(cache_key)
                    if cached:
                        return cached == "1", None
                except Exception:
                    pass  # Игнорируем ошибки Redis
            
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            # Проверяем кэш в БД (более свежий)
            if user and not force_check:
                if user.channel_checked_at:
                    time_since_check = datetime.utcnow() - user.channel_checked_at
                    if time_since_check.total_seconds() < settings.CHANNEL_CHECK_CACHE_TTL:
                        # Используем кэшированное значение
                        # Сохраняем в Redis для следующих запросов (если доступен)
                        if redis_client:
                            try:
                                cache_key = f"channel_sub:{user_id}"
                                await redis_client.setex(
                                    cache_key,
                                    settings.CHANNEL_CHECK_CACHE_TTL,
                                    "1" if user.channel_subscribed else "0"
                                )
                            except Exception:
                                pass  # Игнорируем ошибки Redis
                        return user.channel_subscribed, None
            
            # Выполняем реальную проверку через Telegram API
            channel_id = settings.REQUIRED_CHANNEL_ID
            if channel_id.startswith("@"):
                channel_id = channel_id[1:]  # Убираем @
            
            try:
                member = await bot.get_chat_member(
                    chat_id=channel_id,
                    user_id=user_id
                )
                
                # Проверяем статус подписки
                is_subscribed = member.status in ["member", "administrator", "creator"]
                
                # Обновляем кэш (если Redis доступен)
                if redis_client:
                    try:
                        cache_key = f"channel_sub:{user_id}"
                        await redis_client.setex(
                            cache_key,
                            settings.CHANNEL_CHECK_CACHE_TTL,
                            "1" if is_subscribed else "0"
                        )
                    except Exception:
                        pass  # Игнорируем ошибки Redis
                
                # Обновляем в БД
                if user:
                    user.channel_subscribed = is_subscribed
                    user.channel_checked_at = datetime.utcnow()
                    await session.commit()
                
                return is_subscribed, None
                
            except Exception as e:
                logger.error(f"Ошибка при проверке подписки через Telegram API: {e}")
                # Если ошибка API, используем кэшированное значение
                if user and user.channel_subscribed:
                    return True, None
                return False, "Ошибка при проверке подписки. Попробуйте позже."
                
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки: {e}")
            # При ошибке разрешаем доступ (fail-open)
            return True, None
    
    async def get_channel_link(self) -> str:
        """Возвращает ссылку на канал"""
        if settings.REQUIRED_CHANNEL_USERNAME:
            return f"https://t.me/{settings.REQUIRED_CHANNEL_USERNAME}"
        elif settings.REQUIRED_CHANNEL_ID:
            channel_id = settings.REQUIRED_CHANNEL_ID
            if channel_id.startswith("@"):
                return f"https://t.me/{channel_id[1:]}"
            return channel_id
        return ""


channel_check_service = ChannelCheckService()
