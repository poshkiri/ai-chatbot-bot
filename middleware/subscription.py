"""
Middleware для проверки подписки на канал
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from services.channel_check import channel_check_service
from config import settings

logger = logging.getLogger(__name__)


class SubscriptionCheckMiddleware(BaseMiddleware):
    """Middleware для проверки подписки на канал"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Если канал не указан, пропускаем проверку
        if not settings.REQUIRED_CHANNEL_ID:
            return await handler(event, data)
        
        # Получаем user_id из события
        user_id = None
        chat_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            chat_id = event.message.chat.id if event.message else None
        
        if not user_id or not chat_id:
            return await handler(event, data)
        
        # Получаем бота и сессию из data
        bot: Bot = data.get("bot")
        session: AsyncSession = data.get("session")
        
        if not bot or not session:
            return await handler(event, data)
        
        # Проверяем подписку
        is_subscribed, error_message = await channel_check_service.check_subscription(
            bot=bot,
            user_id=user_id,
            session=session,
            force_check=False
        )
        
        if not is_subscribed:
            channel_link = await channel_check_service.get_channel_link()
            text = (
                "📢 Для использования бота необходимо подписаться на наш канал.\n\n"
                f"Подпишитесь здесь: {channel_link}\n\n"
                "После подписки вернитесь и попробуйте снова."
            )
            
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            
            return None
        
        return await handler(event, data)

