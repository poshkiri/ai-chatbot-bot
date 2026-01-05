"""Middleware для обработки ошибок"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware для глобальной обработки ошибок"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except TelegramRetryAfter as e:
            # Обработка flood wait - ждем указанное время
            logger.warning(f"Flood wait: {e.retry_after} секунд")
            return None
        except TelegramBadRequest as e:
            # Ошибка запроса к Telegram API
            logger.error(f"Telegram Bad Request: {e}")
            return None
        except TelegramNetworkError as e:
            # Ошибка сети
            logger.error(f"Telegram Network Error: {e}")
            return None
        except Exception as e:
            # Общая обработка ошибок
            logger.error(f"Необработанная ошибка: {e}", exc_info=True)
            return None

