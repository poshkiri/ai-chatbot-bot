"""
Обработчики callback запросов (кнопки)
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from database.models import User, Conversation, SubscriptionStatus
from keyboards.common import (
    get_main_menu_keyboard, 
    get_subscription_keyboard, 
    get_conversations_keyboard,
    get_settings_keyboard
)
from services.telegram_payments import payment_service
from services.analytics import analytics_service
from config import settings

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "buy_subscription")
async def callback_buy_subscription(callback: CallbackQuery, bot: Bot, session: AsyncSession):
    """Покупка подписки"""
    user_id = callback.from_user.id
    
    await payment_service.create_subscription_invoice(
        bot=bot,
        chat_id=callback.message.chat.id,
        user_id=user_id
    )
    
    await callback.answer()


@router.callback_query(F.data == "subscription_info")
async def callback_subscription_info(callback: CallbackQuery, session: AsyncSession):
    """Информация о подписке"""
    user_id = callback.from_user.id
    
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Ошибка!", show_alert=True)
        return
    
    is_active = (
        user.subscription_status == SubscriptionStatus.ACTIVE
        and user.subscription_expires_at
        and user.subscription_expires_at > datetime.utcnow()
    )
    
    if is_active:
        text = (
            f"💎 Подписка Premium\n\n"
            f"✅ Статус: Активна\n"
            f"📅 Истекает: {user.subscription_expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Преимущества:\n"
            f"• Неограниченные запросы\n"
            f"• Приоритетная обработка\n"
            f"• Увеличенные лимиты"
        )
    else:
        text = (
            f"💎 Подписка Premium\n\n"
            f"❌ Статус: Неактивна\n\n"
            f"Преимущества подписки:\n"
            f"• Неограниченные запросы к AI\n"
            f"• Приоритетная обработка\n"
            f"• Увеличенные лимиты\n"
            f"• Доступ к новым функциям\n\n"
            f"Цена: ${settings.SUBSCRIPTION_PRICE / 100:.2f} на {settings.SUBSCRIPTION_DURATION_DAYS} дней"
        )
    
    await callback.message.edit_text(text, reply_markup=get_subscription_keyboard(is_active=is_active))
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def callback_back_to_menu(callback: CallbackQuery, session: AsyncSession):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        await callback.answer("Ошибка!", show_alert=True)
        return
    
    is_paid = (
        user.subscription_status == SubscriptionStatus.ACTIVE
        and user.subscription_expires_at
        and user.subscription_expires_at > datetime.utcnow()
    )
    
    text = "🏠 Главное меню\n\nВыберите действие:"
    
    await callback.message.edit_text(text, reply_markup=None)
    await callback.message.answer(text, reply_markup=get_main_menu_keyboard(is_paid=is_paid))
    await callback.answer()


@router.callback_query(F.data == "stats")
async def callback_stats(callback: CallbackQuery, session: AsyncSession):
    """Статистика пользователя"""
    user_id = callback.from_user.id
    
    stats = await analytics_service.get_user_stats(user_id, session)
    
    if not stats:
        await callback.answer("Статистика недоступна", show_alert=True)
        return
    
    stats_text = (
        "📊 Ваша статистика\n\n"
        f"Всего сообщений: {stats.get('total_messages', 0)}\n"
        f"Использовано токенов: {stats.get('total_tokens', 0):,}\n"
        f"Изображений: {stats.get('total_images', 0)}\n"
        f"Аудио: {stats.get('total_audio', 0)}\n"
    )
    
    await callback.message.edit_text(stats_text, reply_markup=get_settings_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("conversation_"))
async def callback_conversation(callback: CallbackQuery, session: AsyncSession):
    """Просмотр диалога"""
    conv_id = int(callback.data.split("_")[1])
    
    result = await session.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        await callback.answer("Диалог не найден", show_alert=True)
        return
    
    text = f"📚 Диалог: {conversation.title or f'#{conversation.id}'}\n\n"
    text += f"Сообщений: {conversation.message_count}\n"
    text += f"Создан: {conversation.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    await callback.message.edit_text(text)
    await callback.answer()

