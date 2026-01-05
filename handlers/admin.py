"""
Обработчики административных функций
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from database.models import User, Message as MessageModel, Payment, SubscriptionStatus
from services.analytics import analytics_service
from config import settings

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    """Админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Получаем статистику
    stats = await analytics_service.get_bot_stats(session)
    
    text = (
        "👨‍💼 Админ-панель\n\n"
        f"📊 Статистика бота:\n"
        f"Всего пользователей: {stats.get('total_users', 0)}\n"
        f"Активных: {stats.get('active_users', 0)}\n"
        f"С подпиской: {stats.get('paid_users', 0)}\n"
        f"Всего сообщений: {stats.get('total_messages', 0)}\n"
        f"Использовано токенов: {stats.get('total_tokens', 0):,}\n"
        f"Платежей: {stats.get('total_payments', 0)}\n"
        f"Выручка: ${stats.get('total_revenue_cents', 0) / 100:.2f}\n\n"
        f"Доступные команды:\n"
        f"/admin_stats - Подробная статистика\n"
        f"/admin_broadcast - Рассылка сообщений"
    )
    
    await message.answer(text)


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message, session: AsyncSession):
    """Подробная статистика"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    stats = await analytics_service.get_bot_stats(session)
    
    # Подсчитываем пользователей по статусам
    free_users = await session.execute(
        select(func.count(User.id)).where(User.subscription_status == SubscriptionStatus.FREE)
    )
    trial_users = await session.execute(
        select(func.count(User.id)).where(User.subscription_status == SubscriptionStatus.TRIAL)
    )
    active_subscriptions = await session.execute(
        select(func.count(User.id)).where(
            User.subscription_status == SubscriptionStatus.ACTIVE,
            User.subscription_expires_at > datetime.utcnow()
        )
    )
    
    text = (
        "📊 Подробная статистика\n\n"
        f"👥 Пользователи:\n"
        f"Всего: {stats.get('total_users', 0)}\n"
        f"Активных: {stats.get('active_users', 0)}\n"
        f"Бесплатных: {free_users.scalar() or 0}\n"
        f"Пробный период: {trial_users.scalar() or 0}\n"
        f"С подпиской: {active_subscriptions.scalar() or 0}\n\n"
        f"💬 Сообщения:\n"
        f"Всего: {stats.get('total_messages', 0)}\n"
        f"Токенов использовано: {stats.get('total_tokens', 0):,}\n\n"
        f"💰 Платежи:\n"
        f"Всего: {stats.get('total_payments', 0)}\n"
        f"Выручка: ${stats.get('total_revenue_cents', 0) / 100:.2f}"
    )
    
    await message.answer(text)


@router.message(Command("admin_broadcast"))
async def cmd_admin_broadcast(message: Message, session: AsyncSession):
    """Рассылка сообщений (упрощенная версия)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await message.answer(
        "📢 Рассылка сообщений\n\n"
        "Используйте: /broadcast <текст сообщения>\n"
        "Пример: /broadcast Привет всем пользователям!"
    )

