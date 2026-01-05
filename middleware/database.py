from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.connection import async_session_maker, get_mongodb
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для инъекции сессии БД в обработчики"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Инжектим SQLAlchemy сессию и MongoDB
        async with async_session_maker() as session:
            try:
                data["session"] = session  # SQLAlchemy сессия
                data["database"] = await get_mongodb()  # MongoDB база данных
                return await handler(event, data)
            except Exception as e:
                # Откатываем транзакцию при ошибке
                await session.rollback()
                raise

