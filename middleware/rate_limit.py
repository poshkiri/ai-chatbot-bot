"""
Middleware для rate limiting
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from services.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """Middleware для проверки rate limits"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        
        if not user_id:
            return await handler(event, data)
        
        # Получаем сессию из data
        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)
        
        # Проверяем rate limit
        allowed, error_message = await rate_limiter.check_rate_limit(
            user_id=user_id,
            session=session,
            operation_type="message"
        )
        
        if not allowed:
            # Отправляем сообщение об ошибке
            if isinstance(event, Message):
                await event.answer(
                    f"⏱️ {error_message}\n\n"
                    "Пожалуйста, подождите немного перед следующим запросом."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"⏱️ {error_message}",
                    show_alert=True
                )
            return None
        
        return await handler(event, data)

