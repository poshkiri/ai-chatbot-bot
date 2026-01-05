"""
Сервис для работы с Telegram Payments
"""
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message, SuccessfulPayment
from aiogram import Bot
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User, Payment, SubscriptionStatus
from config import settings
import logging

logger = logging.getLogger(__name__)


class TelegramPaymentService:
    """Сервис для работы с Telegram Payments"""
    
    def __init__(self):
        self.provider_token = settings.PAYMENT_PROVIDER_TOKEN
        if not self.provider_token:
            logger.warning("PAYMENT_PROVIDER_TOKEN не установлен. Платежи работать не будут.")
    
    async def create_subscription_invoice(
        self, 
        bot: Bot, 
        chat_id: int, 
        user_id: int
    ) -> None:
        """Создает инвойс для подписки"""
        if not self.provider_token:
            await bot.send_message(
                chat_id,
                "❌ Платежи временно недоступны. Пожалуйста, свяжитесь с администратором."
            )
            return
        
        prices = [LabeledPrice(label="Подписка на месяц", amount=settings.SUBSCRIPTION_PRICE)]
        
        try:
            await bot.send_invoice(
                chat_id=chat_id,
                title="💎 Подписка Premium",
                description=(
                    "Подписка включает:\n"
                    "• Неограниченные запросы к AI\n"
                    "• Приоритетная обработка\n"
                    "• Увеличенные лимиты\n"
                    "• Доступ к новым функциям"
                ),
                payload=f"subscription_{user_id}_{int(datetime.utcnow().timestamp())}",
                provider_token=self.provider_token,
                currency="USD",
                prices=prices,
                start_parameter=f"subscription_{user_id}",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                is_flexible=False,
            )
        except Exception as e:
            logger.error(f"Ошибка при создании инвойса: {e}")
            await bot.send_message(
                chat_id,
                "❌ Ошибка при создании счета. Попробуйте позже или свяжитесь с поддержкой."
            )
    
    async def process_pre_checkout(
        self,
        pre_checkout_query: PreCheckoutQuery,
        bot: Bot,
        session: AsyncSession
    ) -> None:
        """Обработка запроса перед оплатой"""
        try:
            await bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=True
            )
            logger.info(f"Pre-checkout подтвержден: {pre_checkout_query.id}")
        except Exception as e:
            logger.error(f"Ошибка при обработке pre-checkout: {e}")
            await bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="Ошибка при обработке платежа"
            )
    
    async def process_successful_payment(
        self,
        message: Message,
        payment: SuccessfulPayment,
        session: AsyncSession
    ) -> None:
        """Обработка успешного платежа"""
        user_id = message.from_user.id
        payload = payment.invoice_payload
        
        if not payload.startswith("subscription_"):
            return
        
        try:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.error(f"Пользователь {user_id} не найден при обработке платежа")
                return
            
            # Создаем запись о платеже
            payment_record = Payment(
                user_id=user.id,
                amount=payment.total_amount,
                currency=payment.currency,
                telegram_payment_charge_id=payment.telegram_payment_charge_id,
                provider_payment_charge_id=payment.provider_payment_charge_id,
                status="completed",
                subscription_duration_days=settings.SUBSCRIPTION_DURATION_DAYS,
                completed_at=datetime.utcnow()
            )
            session.add(payment_record)
            
            # Обновляем подписку пользователя
            expires_at = datetime.utcnow() + timedelta(days=settings.SUBSCRIPTION_DURATION_DAYS)
            user.subscription_status = SubscriptionStatus.ACTIVE
            user.subscription_expires_at = expires_at
            
            await session.commit()
            
            logger.info(f"Подписка активирована для пользователя {user_id}")
            
            await message.answer(
                f"✅ Подписка активирована до {expires_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                "Теперь у вас есть доступ ко всем функциям бота!"
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке платежа: {e}")
            await session.rollback()
            await message.answer(
                "❌ Ошибка при активации подписки. Пожалуйста, свяжитесь с поддержкой."
            )


payment_service = TelegramPaymentService()

