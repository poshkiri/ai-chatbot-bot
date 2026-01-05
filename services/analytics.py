"""
Сервис для аналитики использования бота
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User, Analytics, Message, Payment, SubscriptionStatus
from config import settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Сервис для аналитики"""
    
    async def log_event(
        self,
        event_type: str,
        user_id: Optional[int],
        event_data: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ):
        """Логирует событие в аналитику"""
        if not settings.ANALYTICS_ENABLED or not session:
            return
        
        try:
            user_db_id = None
            if user_id:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    user_db_id = user.id
            
            analytics_event = Analytics(
                user_id=user_db_id,
                event_type=event_type,
                event_data=event_data or {}
            )
            session.add(analytics_event)
            await session.commit()
        except Exception as e:
            logger.error(f"Ошибка при логировании события: {e}")
            if session:
                await session.rollback()
    
    async def get_user_stats(
        self,
        user_id: int,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Возвращает статистику пользователя"""
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return {}
        
        # Подсчитываем сообщения
        messages_count = await session.execute(
            select(func.count(Message.id)).where(Message.user_id == user.id)
        )
        
        # Подсчитываем токены и стоимость
        tokens_sum = await session.execute(
            select(func.sum(Message.tokens_used)).where(Message.user_id == user.id)
        )
        
        cost_sum = await session.execute(
            select(func.sum(Message.cost_estimated)).where(Message.user_id == user.id)
        )
        
        return {
            "total_messages": messages_count.scalar() or 0,
            "total_tokens": tokens_sum.scalar() or 0,
            "total_cost_cents": cost_sum.scalar() or 0,
            "total_images": user.total_images_sent,
            "total_audio": user.total_audio_sent,
            "subscription_status": user.subscription_status.value,
            "free_messages_used": user.free_messages_used,
            "trial_messages_used": user.trial_messages_used,
        }
    
    async def get_bot_stats(
        self,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """Возвращает общую статистику бота"""
        # Всего пользователей
        total_users = await session.execute(select(func.count(User.id)))
        
        # Активных пользователей
        active_users = await session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        
        # Пользователей с активной подпиской
        paid_users = await session.execute(
            select(func.count(User.id)).where(
                User.subscription_status == SubscriptionStatus.ACTIVE,
                User.subscription_expires_at > datetime.utcnow()
            )
        )
        
        # Всего сообщений
        total_messages = await session.execute(select(func.count(Message.id)))
        
        # Всего токенов
        total_tokens = await session.execute(select(func.sum(Message.tokens_used)))
        
        # Всего платежей
        total_payments = await session.execute(
            select(func.count(Payment.id)).where(Payment.status == "completed")
        )
        
        # Общая сумма платежей
        total_revenue = await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "completed")
        )
        
        return {
            "total_users": total_users.scalar() or 0,
            "active_users": active_users.scalar() or 0,
            "paid_users": paid_users.scalar() or 0,
            "total_messages": total_messages.scalar() or 0,
            "total_tokens": total_tokens.scalar() or 0,
            "total_payments": total_payments.scalar() or 0,
            "total_revenue_cents": total_revenue.scalar() or 0,
        }


analytics_service = AnalyticsService()

