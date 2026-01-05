"""
Обработчики сообщений пользователей
"""
import asyncio
import logging
from typing import Tuple
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from database.models import User, Conversation, Message as MessageModel, MessageType, SubscriptionStatus
from services.ai_service import ai_service
from services.analytics import analytics_service
from config import settings

router = Router()
logger = logging.getLogger(__name__)


async def get_or_create_conversation(user_id: int, session: AsyncSession) -> Conversation:
    """Получает или создает активный диалог пользователя"""
    # Получаем пользователя
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError("Пользователь не найден")
    
    # Ищем активный диалог
    result = await session.execute(
        select(Conversation).where(
            Conversation.user_id == user.id,
            Conversation.is_active == True,
            Conversation.is_archived == False
        ).order_by(Conversation.created_at.desc())
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        # Создаем новый диалог
        conversation = Conversation(
            user_id=user.id,
            title="Новый диалог",
            is_active=True
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
    
    return conversation


async def check_user_limits(user: User) -> Tuple[bool, str]:
    """Проверяет лимиты пользователя"""
    is_paid = (
        user.subscription_status == SubscriptionStatus.ACTIVE
        and user.subscription_expires_at
        and user.subscription_expires_at > datetime.utcnow()
    )
    
    if is_paid:
        return True, None
    
    # Проверяем пробный период
    if user.subscription_status == SubscriptionStatus.TRIAL:
        if user.trial_messages_used >= user.trial_messages_limit:
            return False, "Пробный период истек. Оформите подписку для продолжения."
        return True, None
    
    # Проверяем бесплатный лимит
    if user.free_messages_used >= user.free_messages_limit:
        return False, (
            f"Бесплатный лимит исчерпан ({user.free_messages_limit} сообщений).\n\n"
            "Оформите подписку для неограниченных запросов!"
        )
    
    return True, None


async def show_typing_action(bot: Bot, chat_id: int, duration: int = settings.TYPING_ACTION_DURATION):
    """Показывает индикатор 'печатает...'"""
    if not settings.ENABLE_TYPING_ACTION:
        return
    
    try:
        # Отправляем typing action каждые 5 секунд
        end_time = asyncio.get_event_loop().time() + duration
        while asyncio.get_event_loop().time() < end_time:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(5)
    except Exception as e:
        logger.warning(f"Ошибка при отправке typing action: {e}")


@router.message(F.text)
async def process_text_message(message: Message, bot: Bot, session: AsyncSession, state: FSMContext):
    """Обработка текстовых сообщений"""
    user_id = message.from_user.id
    text = message.text
    
    # Проверяем команды (они обрабатываются отдельно)
    if text.startswith("/"):
        return
    
    try:
        # Получаем пользователя
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Пожалуйста, начните с команды /start")
            return
        
        # Проверяем лимиты
        allowed, error_message = await check_user_limits(user)
        if not allowed:
            await message.answer(error_message)
            return
        
        # Получаем или создаем диалог
        conversation = await get_or_create_conversation(user_id, session)
        
        # Показываем индикатор печати
        typing_task = None
        if settings.ENABLE_TYPING_ACTION:
            typing_task = asyncio.create_task(
                show_typing_action(bot, message.chat.id, settings.TYPING_ACTION_DURATION)
            )
        
        # Получаем историю диалога для контекста
        history_result = await session.execute(
            select(MessageModel).where(
                MessageModel.conversation_id == conversation.id
            ).order_by(MessageModel.created_at.desc()).limit(10)
        )
        history_messages = history_result.scalars().all()
        
        # Формируем историю для AI
        conversation_history = []
        for msg in reversed(history_messages):  # Реверс для хронологического порядка
            role = "user" if msg.is_from_user else "assistant"
            content = msg.content or msg.ai_response or ""
            if content:
                conversation_history.append({"role": role, "content": content})
        
        # Обрабатываем через AI
        try:
            ai_result = await ai_service.process_text(
                prompt=text,
                user_id=user_id,
                conversation_history=conversation_history if conversation_history else None,
                session=session
            )
            
            ai_response = ai_result.get("response", "Извините, не удалось получить ответ.")
            
            # Останавливаем typing action
            if typing_task:
                typing_task.cancel()
            
            # Сохраняем сообщение пользователя
            user_message = MessageModel(
                conversation_id=conversation.id,
                user_id=user.id,
                message_type=MessageType.TEXT,
                content=text,
                is_from_user=True
            )
            session.add(user_message)
            
            # Сохраняем ответ AI
            ai_message = MessageModel(
                conversation_id=conversation.id,
                user_id=user.id,
                message_type=MessageType.TEXT,
                content=ai_response,
                is_from_user=False,
                ai_response=ai_response,
                tokens_used=ai_result.get("tokens_used", 0),
                cost_estimated=ai_service.estimate_cost(
                    ai_result.get("tokens_used", 0),
                    ai_result.get("model", "")
                ),
                processing_time=ai_result.get("processing_time", 0)
            )
            session.add(ai_message)
            
            # Обновляем счетчики диалога
            conversation.message_count += 2
            conversation.last_message_at = datetime.utcnow()
            conversation.updated_at = datetime.utcnow()
            
            # Обновляем счетчики пользователя
            user.total_messages_sent += 1
            user.total_tokens_used += ai_result.get("tokens_used", 0)
            user.total_cost_estimated += ai_service.estimate_cost(
                ai_result.get("tokens_used", 0),
                ai_result.get("model", "")
            )
            user.last_activity_at = datetime.utcnow()
            
            # Обновляем лимиты
            if user.subscription_status == SubscriptionStatus.TRIAL:
                user.trial_messages_used += 1
            elif user.subscription_status == SubscriptionStatus.FREE:
                user.free_messages_used += 1
            
            await session.commit()
            
            # Логируем событие
            await analytics_service.log_event(
                "message_sent",
                user_id,
                {
                    "type": "text",
                    "tokens": ai_result.get("tokens_used", 0),
                    "processing_time": ai_result.get("processing_time", 0)
                },
                session=session
            )
            
            # Отправляем ответ
            await message.answer(ai_response)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке AI запроса: {e}", exc_info=True)
            if typing_task:
                typing_task.cancel()
            await message.answer("❌ Произошла ошибка при обработке запроса. Попробуйте позже.")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)
        await session.rollback()
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(F.photo)
async def process_photo_message(message: Message, bot: Bot, session: AsyncSession):
    """Обработка изображений"""
    await message.answer(
        "🖼️ Обработка изображений пока не реализована.\n"
        "Эта функция будет добавлена в ближайшее время."
    )


@router.message(F.voice | F.audio)
async def process_audio_message(message: Message, bot: Bot, session: AsyncSession):
    """Обработка аудио сообщений"""
    await message.answer(
        "🎤 Обработка аудио сообщений пока не реализована.\n"
        "Эта функция будет добавлена в ближайшее время."
    )

