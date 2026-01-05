"""
Обработчики команд бота
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from database.models import User, Conversation, SubscriptionStatus
from keyboards.common import get_main_menu_keyboard, get_subscription_keyboard, get_settings_keyboard
from services.analytics import analytics_service
from config import settings

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    user_id = message.from_user.id
    
    # Проверяем, существует ли пользователь
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        # Создаем нового пользователя
        user = User(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language='ru'
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        # Логируем событие
        await analytics_service.log_event("user_registered", user_id, session=session)
        
        welcome_text = (
            "👋 Добро пожаловать в AI-бота!\n\n"
            "Я помогу вам с любыми вопросами. Просто напишите мне сообщение.\n\n"
            "Доступно бесплатных сообщений: 10"
        )
    else:
        # Обновляем информацию о пользователе
        user.username = message.from_user.username
        user.first_name = message.from_user.first_name
        user.last_name = message.from_user.last_name
        user.last_activity_at = datetime.utcnow()
        await session.commit()
        
        welcome_text = (
            "👋 С возвращением!\n\n"
            f"Доступно бесплатных сообщений: {user.free_messages_limit - user.free_messages_used}"
        )
    
    is_paid = (
        user.subscription_status == SubscriptionStatus.ACTIVE
        and user.subscription_expires_at
        and user.subscription_expires_at > datetime.utcnow()
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(is_paid=is_paid)
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "📖 Справка по использованию бота\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/stats - Показать статистику\n\n"
        "Функции:\n"
        "💬 Начать диалог - начать новый диалог с AI\n"
        "📚 История диалогов - просмотр предыдущих диалогов\n"
        "⚙️ Настройки - настройки бота\n"
        "💎 Подписка - информация о подписке\n\n"
        "Поддерживаются:\n"
        "• Текстовые сообщения\n"
        "• Изображения\n"
        "• Аудио сообщения"
    )
    await message.answer(help_text)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    """Показывает статистику пользователя"""
    user_id = message.from_user.id
    
    stats = await analytics_service.get_user_stats(user_id, session)
    
    if not stats:
        await message.answer("❌ Статистика недоступна. Начните с /start")
        return
    
    stats_text = (
        "📊 Ваша статистика\n\n"
        f"Всего сообщений: {stats.get('total_messages', 0)}\n"
        f"Использовано токенов: {stats.get('total_tokens', 0):,}\n"
        f"Изображений отправлено: {stats.get('total_images', 0)}\n"
        f"Аудио отправлено: {stats.get('total_audio', 0)}\n"
        f"Статус подписки: {stats.get('subscription_status', 'free')}\n"
    )
    
    if stats.get('subscription_status') == 'free':
        stats_text += f"\nИспользовано бесплатных сообщений: {stats.get('free_messages_used', 0)}/{settings.FREE_MESSAGES_LIMIT}"
    
    await message.answer(stats_text)

